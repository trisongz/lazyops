"""
Modified from https://github.com/michalc/stream-inflate/blob/main/stream_inflate.py
"""

from queue import Empty, Queue
from collections import Counter, defaultdict, namedtuple
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

# An object that can be seen as a "deferred" that can pause a generator, with
# the extra abiliy to yield values by the generator "runner".
DeferredYielder = namedtuple(
    'DeferredYielder', (
        'can_proceed',
        'to_yield',
        'num_from_cache',
        'return_value',
    )
)

class UnsupportedBlockType(Exception):
    pass


class IterableQueue:
    def __init__(self, **kwargs):
        self.queue = Queue()
        self.iterable: Optional[Iterable] = None
    
    def append(self, iterable: Iterable):
        """
        Appends an iterable to the queue
        """
        self.queue.put_nowait(iterable)

    def next(self) -> Optional[Iterable]:
        """
        Gets the next iterable
        """
        while True:
            if self.iterable is None:
                try:
                    self.iterable = iter(self.queue.get_nowait())
                except Empty:
                    raise StopIteration() from None
                else:
                    self.queue.task_done()
            
            try:
                return next(self.iterable)
            except StopIteration:
                self.iterable = None
    
    def __iter__(self):
        return self
    
    def __next__(self):
        return self.next()
    

class BitByteReader:
    def __init__(self, iter_queue: IterableQueue, **kwargs):
        self.iter_queue = iter_queue
        self.post_init(**kwargs)

    def post_init_constants(self, **kwargs):
        """
        Initializes the constants
        """
        self.chunk = b''
        self.offset_byte = 0
        self.offset_bit = 0

    def post_init(self, **kwargs):
        """
        Post initialization hook.
        """
        self.post_init_constants(**kwargs)

    def has_bit(self) -> bool:
        """
        Returns whether or not there is a bit
        """
        if self.offset_bit == 8:
            self.offset_bit = 0
            self.offset_byte += 1

        if self.offset_byte == len(self.chunk):
            try:
                self.chunk = self.iter_queue.next()
            except StopIteration:
                return False
            else:
                self.offset_byte = 0
                self.offset_bit = 0
        return True
    
    def has_byte(self) -> bool:
        """
        Returns whether or not there is a byte
        """
        if self.offset_bit:
            self.offset_byte += 1
        self.offset_bit = 0
        return self.has_bit()

    def get_bit(self) -> int:
        """
        Gets the bit
        """
        self.offset_bit += 1
        return (self.chunk[self.offset_byte] & (2 ** (self.offset_bit - 1))) >> (self.offset_bit - 1)

    def get_byte(self) -> int:
        """
        Gets the byte
        """
        self.offset_byte += 1
        return self.chunk[self.offset_byte - 1]
    
    def yield_bytes_up_to(self, num_bytes: int) -> Generator[bytes, None, None]:
        """
        Yields bytes up to the number of bytes
        """
        if self.offset_bit: self.offset_byte += 1
        self.offset_bit = 0
        while num_bytes:
            if self.offset_byte == len(self.chunk):
                try:
                    self.chunk = self.iter_queue.next()
                except StopIteration:
                    return
                self.offset_byte = 0
            to_yield = min(num_bytes, len(self.chunk) - self.offset_byte)
            self.offset_byte += to_yield
            num_bytes -= to_yield
            yield self.chunk[self.offset_byte - to_yield:self.offset_byte]

    def num_bytes_unconsumed(self) -> int:
        """
        Returns the number of bytes unconsumed
        """
        return len(self.chunk) - self.offset_byte - (1 if self.offset_bit else 0)

class DeferredBitByteReader:
    def __init__(
        self, 
        reader: BitByteReader,
        **kwargs
    ):
        self.reader = reader
        self.post_init(**kwargs)

    def post_init_constants(self, **kwargs):
        """
        Initializes the constants
        """
        self.get_bit = DeferredYielder(
            can_proceed = self.reader.has_bit, 
            to_yield = lambda: (), 
            num_from_cache = lambda: (0, 0), 
            return_value = self.reader.get_bit
        )
        self.get_byte = DeferredYielder(
            can_proceed = self.reader.has_byte, 
            to_yield = lambda: (), 
            num_from_cache = lambda: (0, 0), 
            return_value = self.reader.get_byte
        )

    def post_init(self, **kwargs):
        """
        Post initialization hook.
        """
        self.post_init_constants(**kwargs)

    def get_bits(self, num_bits: int) -> bytes:
        """
        Gets the bits
        """
        out = bytearray(- ( - num_bits // 8 ))
        out_offset_bit = 0
        while num_bits:
            bit = yield self.get_bit
            out[out_offset_bit // 8] |= bit << (out_offset_bit % 8)
            num_bits -= 1
            out_offset_bit += 1
        return bytes(out)
    
    def get_bytes(self, num_bytes: int) -> bytes:
        """
        Gets the bytes
        """
        out = bytearray(num_bytes)
        out_offset_byte = 0
        while out_offset_byte != num_bytes:
            out[out_offset_byte] = yield self.get_byte
            out_offset_byte += 1
        return bytes(out)

    def yield_bytes(self, num_bytes: int) -> Generator[bytes, None, None]:
        """
        Yields the bytes
        """

        def to_yield():
            nonlocal num_bytes
            for chunk in self.reader.yield_bytes_up_to(num_bytes):
                num_bytes -= len(chunk)
                yield chunk
        
        yield_bytes_up_to = DeferredYielder(
            can_proceed = self.reader.has_byte, 
            to_yield = to_yield, 
            num_from_cache = lambda: (0, 0), 
            return_value = lambda: None
        )

        while num_bytes:
            yield yield_bytes_up_to

class BackwardsCache:
    def __init__(self, size: int, **kwargs):
        self.size = size
        self.cache = bytearray(size)
        self.cache_start = 0
        self.cache_len = 0

    def via_cache(self, bytes_iter: Iterable) -> Generator[bytes, None, None]:
        """
        Yields bytes via the cache
        """
        for chunk in bytes_iter:
            chunk_start = max(len(chunk) - self.size, 0)
            chunk_end = len(chunk)
            chunk_len = chunk_end - chunk_start
            part_1_start = (self.cache_start + self.cache_len) % self.size
            part_1_end = min(part_1_start + chunk_len, self.size)
            part_1_chunk_start = chunk_start
            part_1_chunk_end = chunk_start + (part_1_end - part_1_start)
            part_2_start = 0
            part_2_end = chunk_len - (part_1_end - part_1_start)
            part_2_chunk_start = part_1_chunk_end
            part_2_chunk_end = part_1_chunk_end + (part_2_end - part_2_start)

            cache_len_over_size = max((self.cache_len + chunk_len) - self.size, 0)
            self.cache_len = min(self.size, self.cache_len + chunk_len)
            self.cache_start = (self.cache_start + cache_len_over_size) % self.size

            self.cache[part_1_start:part_1_end] = chunk[part_1_chunk_start:part_1_chunk_end]
            self.cache[part_2_start:part_2_end] = chunk[part_2_chunk_start:part_2_chunk_end]
            yield chunk

    def from_cache(self, dist: int, length: int) -> Generator[bytes, None, None]:
        """
        Yields bytes from the cache
        """
        if dist > self.cache_len:
            raise ValueError('Searching backwards too far', dist, len(self.cache))

        available = dist
        part_1_start = (self.cache_start + self.cache_len - dist) % self.size
        part_1_end = min(part_1_start + available, self.size)
        part_2_start = 0
        part_2_end = max(available - (part_1_end - part_1_start), 0)

        while length:
            to_yield = self.cache[part_1_start:part_1_end][:length]
            length -= len(to_yield)
            yield to_yield
            to_yield = self.cache[part_2_start:part_2_end][:length]
            length -= len(to_yield)
            yield to_yield

class StreamRunner:
    def __init__(
        self,
        iter_queue: IterableQueue,
        cache: BackwardsCache,
        alg: Generator[DeferredYielder, None, Tuple[bool, Optional[bytes], int, Callable[[], Any]]],
        **kwargs,
    ):
        self.iter_queue = iter_queue
        self.cache = cache
        self.alg = alg

        self.is_done = False
        self.can_proceed, self.to_yield, self.num_from_cache, self.return_value  = None, None, None, None

    def run(self, iterable: Iterable) -> DeferredYielder:
        """
        Runs the iterable
        """
        self.iter_queue.append(iterable)
        while True:
            if self.can_proceed:
                try:
                    self.can_proceed, self.to_yield, self.num_from_cache, self.return_value = \
                            next(self.alg) if self.return_value is None else \
                            self.alg.send(self.return_value())
                except StopIteration:
                    break

            if not self.can_proceed(): return
            yield from self.cache.via_cache(self.to_yield())
            yield from self.cache.via_cache(self.cache.from_cache(*self.num_from_cache()))
            self.can_proceed = None
        self.is_done = True

class Paginator:
    def __init__(
        self,
        runner: StreamRunner,
        page_size: int, # chunk size
    ):
        self.runner = runner
        self.page_size = page_size
    
    def paginate(self, bytes_iter: Iterable) -> Generator[bytes, None, None]:
        """
        Paginates the iterable
        """
        chunk = b''
        offset = 0
        it = iter(bytes_iter)

        def up_to_page_size(num):
            nonlocal chunk, offset
            while num:
                if offset == len(chunk):
                    try:
                        chunk = next(it)
                    except StopIteration:
                        break
                    else:
                        offset = 0
                to_yield = min(num, len(chunk) - offset)
                offset = offset + to_yield
                num -= to_yield
                yield chunk[offset - to_yield:offset]

        while True:
            page = b''.join(up_to_page_size(self.page_size))
            if not page: break
            yield page

    def run(self, *args, **kwargs):
        """
        Runs the paginator
        """
        yield from self.paginate(self.runner.run(*args, **kwargs))

    


class StreamInflate:
    def __init__(
        self, 
        chunk_size: Optional[int] = 65536,
        b64: Optional[bool] = False,
        **kwargs
    ):
        self.chunk_size = chunk_size
        self.b64 = b64
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Handles some post-init stuff
        """
        
        self.post_init_constants(**kwargs)
        self.post_init_objects(**kwargs)


    def post_init_constants(self, **kwargs):
        """
        Initializes the constants
        """
        if self.b64:
            self.cache_size = self.chunk_size
            self.length_extra_bits_diffs = (
                (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
                (1, 11), (1, 13), (1, 15), (1, 17),
                (2, 19), (2, 23), (2, 27), (2, 31),
                (3, 35), (3, 43), (3, 51), (3, 59),
                (4, 67), (4, 83), (4, 99), (4, 115),
                (5, 131), (5, 163), (5, 195), (5, 227),
                (16, 3),
            )
            self.dist_extra_bits_diffs = (
                (0, 1), (0, 2), (0, 3), (0, 4),
                (1, 5), (1, 7), (2, 9), (2, 13),
                (3, 17), (3, 25), (4, 33), (4, 49),
                (5, 65), (5, 97), (6, 129), (6, 193),
                (7, 257), (7, 385), (8, 513), (8, 769),
                (9, 1025), (9, 1537), (10, 2049), (10, 3073),
                (11, 4097), (11, 6145), (12, 8193), (12, 12289),
                (13, 16385), (13, 24577), (14, 32769), (14, 49153),
            )
        
        else:
            self.cache_size = self.chunk_size / 2
            self.length_extra_bits_diffs = (
                (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
                (1, 11), (1, 13), (1, 15), (1, 17),
                (2, 19), (2, 23), (2, 27), (2, 31),
                (3, 35), (3, 43), (3, 51), (3, 59),
                (4, 67), (4, 83), (4, 99), (4, 115),
                (5, 131), (5, 163), (5, 195), (5, 227),
                (0, 258),
            )
            self.dist_extra_bits_diffs = (
                (0, 1), (0, 2), (0, 3), (0, 4),
                (1, 5), (1, 7), (2, 9), (2, 13),
                (3, 17), (3, 25), (4, 33), (4, 49),
                (5, 65), (5, 97), (6, 129), (6, 193),
                (7, 257), (7, 385), (8, 513), (8, 769),
                (9, 1025), (9, 1537), (10, 2049), (10, 3073),
                (11, 4097), (11, 6145), (12, 8193), (12, 12289),
                (13, 16385), (13, 24577),
            )

        self.literal_stop_or_length_code_lengths = \
            (8,) * 144 + \
            (9,) * 112 + \
            (7,) * 24 + \
            (8,) * 8
        self.dist_code_lengths = \
            (5,) * 32
        self.code_lengths_alphabet = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


    def post_init_objects(self, **kwargs):
        """
        Initializes the objects
        """
        self.iter_queue = IterableQueue()
        self.reader = BitByteReader(self.iter_queue)
        self.deferred_reader = DeferredBitByteReader(self.reader)
        self.cache = BackwardsCache(self.cache_size)
        self.runner = StreamRunner(self.iter_queue, self.cache, self.inflate())
        self.paginator = Paginator(self.runner, self.chunk_size)

    def get_huffman_codes(self, lengths: List[int]) -> Dict[Tuple[int, int], int]:

        def yield_codes():
            max_bits = max(lengths)
            bl_count = defaultdict(int, Counter(lengths))
            next_code = {}
            code = 0
            bl_count[0] = 0
            for bits in range(1, max_bits + 1):
                code = (code + bl_count[bits - 1]) << 1
                next_code[bits] = code

            for value, length in enumerate(lengths):
                if length != 0:
                    next_code[length] += 1
                    yield (length, next_code[length] - 1), value

        return dict(yield_codes())
    
    def get_huffman_value(self, codes: Dict[Tuple[int, int], int]) -> Generator[int, None, None]:
        """
        Returns the huffman value
        """
        length = 0
        code = 0
        while True:
            length += 1
            code = (code << 1) | ord((yield from self.deferred_reader.get_bits(1)))
            try:
                return codes[(length, code)]
            except KeyError:
                continue

    def get_code_length_code_lengths(self, num_length_codes: int) -> Generator[Tuple[int, ...], None, None]:
        """
        Returns the code length code lengths
        """
        result = [0] * num_length_codes
        for i in range(num_length_codes):
            result[i] = ord((yield from self.deferred_reader.get_bits(3)))
        return tuple(result)

    def get_code_lengths(self, code_length_codes, num_codes: int) -> Generator[Tuple[int, ...], None, None]:
        """
        Returns the code lengths
        """
        result = [0] * num_codes
        i = 0
        previous = None
        while i < num_codes:
            code = yield from self.get_huffman_value(code_length_codes)
            if code < 16:
                previous = code
                result[i] = code
                i += 1
            elif code == 16:
                for _ in range(3 + ord((yield from self.deferred_reader.get_bits(2)))):
                    result[i] = previous
                    i += 1
            elif code == 17:
                i += 3 + ord((yield from self.deferred_reader.get_bits(3)))
                previous = 0
            elif code == 18:
                i += 11 + ord((yield from self.deferred_reader.get_bits(7)))
                previous = 0
        return result
    

    def yield_exactly(
        self, 
        bytes_to_yield: bytes,
    ) -> Generator[bytes, None, None]:
        """
        Yields exactly the bytes
        """
        return DeferredYielder(can_proceed=lambda: True, to_yield=lambda: (bytes_to_yield,), num_from_cache=lambda: (0, 0), return_value=lambda: None)

    def yield_from_cache(self, dist: int, length: int) -> Generator[bytes, None, None]:
        """
        Yields from the cache
        """
        return DeferredYielder(can_proceed=lambda: True, to_yield=lambda: (), num_from_cache=lambda: (dist, length), return_value=lambda: None)


    def inflate(
        self,
    ):
        """
        The main inflate algorithm.
        """
        b_final = b'\0'

        while not b_final[0]:
            b_final = yield from self.deferred_reader.get_bits(1)
            b_type = yield from self.deferred_reader.get_bits(2)

            if b_type == b'\3':
                raise UnsupportedBlockType(b_type)

            if b_type == b'\0':
                b_len = int.from_bytes((yield from self.deferred_reader.get_bytes(2)), byteorder='little')
                yield from self.deferred_reader.get_bytes(2)
                yield from self.deferred_reader.yield_bytes(b_len)
                continue

            if b_type == b'\1':
                literal_stop_or_length_codes = self.get_huffman_codes(self.literal_stop_or_length_code_lengths)
                backwards_dist_codes = self.get_huffman_codes(self.dist_code_lengths)
            else:
                num_literal_length_codes = ord((yield from self.deferred_reader.get_bits(5))) + 257
                num_dist_codes = ord((yield from self.deferred_reader.get_bits(5))) + 1
                num_length_codes = ord((yield from self.deferred_reader.get_bits(4))) + 4

                code_length_code_lengths = (yield from self.get_code_length_code_lengths(num_length_codes)) + ((0,) * (19 - num_length_codes))
                code_length_code_lengths = tuple(
                    v for i, v in
                    sorted(enumerate(code_length_code_lengths), key=lambda x: self.code_lengths_alphabet[x[0]])
                )
                code_length_codes = self.get_huffman_codes(code_length_code_lengths)

                dynamic_code_lengths = yield from self.get_code_lengths(code_length_codes, num_literal_length_codes + num_dist_codes)
                dynamic_literal_code_lengths = dynamic_code_lengths[:num_literal_length_codes]
                dynamic_dist_code_lengths = dynamic_code_lengths[num_literal_length_codes:]

                literal_stop_or_length_codes = self.get_huffman_codes(dynamic_literal_code_lengths)
                backwards_dist_codes = self.get_huffman_codes(dynamic_dist_code_lengths)

            while True:
                literal_stop_or_length_code = yield from self.get_huffman_value(literal_stop_or_length_codes)
                if literal_stop_or_length_code < 256:
                    yield self.yield_exactly(bytes((literal_stop_or_length_code,)))
                elif literal_stop_or_length_code == 256:
                    break
                else:
                    length_extra_bits, length_diff = self.length_extra_bits_diffs[literal_stop_or_length_code - 257]
                    length_extra = int.from_bytes((yield from self.deferred_reader.get_bits(length_extra_bits)), byteorder='little')

                    code = yield from self.get_huffman_value(backwards_dist_codes)
                    dist_extra_bits, dist_diff = self.dist_extra_bits_diffs[code]
                    dist_extra = int.from_bytes((yield from self.deferred_reader.get_bits(dist_extra_bits)), byteorder='little')

                    yield self.yield_from_cache(dist=dist_extra + dist_diff, length=length_extra + length_diff)

    def is_done(self) -> bool:
        """
        Returns True if the inflation is done
        """
        return self.runner.is_done

    def __call__(self, **kwargs) -> Tuple[Callable[[], Any], Callable[[], bool], Callable[[], int]]:
        """
        Returns the inflate function
        """
        return self.paginator.run, self.is_done, self.reader.num_bytes_unconsumed