import asyncio

from collections import Counter, defaultdict, namedtuple
from queue import Empty, Queue
from typing import Tuple, Iterable, Optional, Union, AsyncIterable
import lazyops.libs.stream_unzip.constants as constants
import lazyops.libs.stream_unzip.exceptions as exceptions

# An object that can be seen as a "deferred" that can pause a generator, with
# the extra abiliy to yield values by the generator "runner".
DeferredYielder = namedtuple('DeferredYielder', (
    'can_proceed',
    'to_yield',
    'num_from_cache',
    'return_value',
))

class StreamInflate:
    def __init__(
        self, 
        _async: Optional[bool] = False,
        chunk_size: Optional[int] = constants.STREAM_INFLATE_CHUNK_SIZE,
        b64: Optional[bool] = False,
    ):
        self.queue: Union[asyncio.Queue, Queue] = asyncio.Queue() if _async else Queue()
        self.is_async = _async
        self.is_b64 = b64
        self.chunk_size = chunk_size
        
        self.cache_size = constants.STREAM_INFLATE64_CACHE_SIZE if self.is_b64 else \
            constants.STREAM_INFLATE_CACHE_SIZE
        
        self.length_extra_bits_diffs = constants.STREAM_INFLATE64_LENGTH_EXTRA_BITS_DIFFS if self.is_b64 else \
            constants.STREAM_INFLATE_LENGTH_EXTRA_BITS_DIFFS
        
        self.dist_extra_bits_diffs = constants.STREAM_INFLATE64_DIST_EXTRA_BITS_DIFFS if self.is_b64 else \
            constants.STREAM_INFLATE_DIST_EXTRA_BITS_DIFFS

        self._init_vars()
    
    def _init_vars(self):
        # iterable Queue Vars
        self.it: Union[Iterable, AsyncIterable] = None
        self.chunk: bytes = b''
        self.offset_byte: int = 0
        self.offset_bit: int = 0

        # Deferred Reader Vars
        self.deferred_get_bit = DeferredYielder(
            can_proceed = self.ahas_bit if self.is_async else self.has_bit, 
            to_yield = lambda: (), 
            num_from_cache = lambda: (0, 0), 
            return_value = self.get_bit,
        )
        self.deferred_get_byte = DeferredYielder(
            can_proceed = self.ahas_byte if self.is_async else self.has_byte,
            to_yield = lambda: (),
            num_from_cache = lambda: (0, 0),
            return_value = self.get_byte,
        )
        # Backwards Cache Vars
        self.cache = bytearray(self.cache_size)
        self.cache_start = 0
        self.cache_len = 0

        # Runner Vars
        self.is_done = False
        self.can_proceed = self.ahas_byte if self.is_async else self.has_byte
        self.to_yield = None
        self.num_from_cache = None
        self.return_value = None


    def append(self, iterable: Iterable):
        self.queue.put_nowait(iterable)
    
    def next(self):
        while True:
            if self.it is None:
                try:
                    self.it = iter(self.queue.get_nowait())
                except Empty:
                    raise StopIteration() from None
                else:
                    self.queue.task_done()
            try:
                return next(self.it)
            except StopIteration:
                self.it = None
    
    async def anext(self):
        while True:
            if self.it is None:
                try:
                    self.it = iter(self.queue.get_nowait())
                except Empty:
                    raise StopIteration() from None
                else:
                    self.queue.task_done()
            try:
                return await self.it.__anext__()
            except StopIteration:
                self.it = None
        
    def has_bit(self) -> bool:
        if self.offset_bit == 8:
            self.offset_bit = 0
            self.offset_byte += 1

        if self.offset_byte == len(self.chunk):
            try:
                self.chunk = self.next()
            except StopIteration:
                return False
            else:
                self.offset_byte = 0
                self.offset_bit = 0
        return True
    
    async def ahas_bit(self) -> bool:
        if self.offset_bit == 8:
            self.offset_bit = 0
            self.offset_byte += 1

        if self.offset_byte == len(self.chunk):
            try:
                self.chunk = await self.anext()
            except StopIteration:
                return False
            else:
                self.offset_byte = 0
                self.offset_bit = 0
        return True

    def has_byte(self) -> bool:
        if self.offset_bit:
            self.offset_byte += 1
        self.offset_bit = 0
        return self.has_bit()

    async def ahas_byte(self) -> bool:
        if self.offset_bit:
            self.offset_byte += 1
        self.offset_bit = 0
        return await self.ahas_bit()

    def get_bit(self) -> int:
        self.offset_bit += 1
        return (self.chunk[self.offset_byte] & (2 ** (self.offset_bit - 1))) >> (self.offset_bit - 1)
    
    def get_byte(self):
        self.offset_byte += 1
        return self.chunk[self.offset_byte - 1]
    
    @property
    def num_bytes_unconsumed(self) -> int:
        return len(self.chunk) - self.offset_byte - (1 if self.offset_bit else 0)
    
    def yield_bytes_up_to(self, num: int):
        if self.offset_bit:
            self.offset_byte += 1
        self.offset_bit = 0

        while num:
            if self.offset_byte == len(self.chunk):
                try:
                    self.chunk = self.next()
                except StopIteration:
                    return
                self.offset_byte = 0
            to_yield = min(num, len(self.chunk) - self.offset_byte)
            self.offset_byte += to_yield
            num -= to_yield
            yield self.chunk[self.offset_byte - to_yield:self.offset_byte]

    async def ayield_bytes_up_to(self, num: int):
        if self.offset_bit:
            self.offset_byte += 1
        self.offset_bit = 0

        while num:
            if self.offset_byte == len(self.chunk):
                try:
                    self.chunk = await self.anext()
                except StopIteration:
                    return
                self.offset_byte = 0
            to_yield = min(num, len(self.chunk) - self.offset_byte)
            self.offset_byte += to_yield
            num -= to_yield
            yield self.chunk[self.offset_byte - to_yield:self.offset_byte]


    def get_bits(self, num_bits: int):
        out = bytearray(-(-num_bits // 8))
        out_offset_bit = 0

        while num_bits:
            bit = yield self.deferred_get_bit
            out[out_offset_bit // 8] |= bit << (out_offset_bit % 8)
            num_bits -= 1
            out_offset_bit += 1

        return bytes(out)

    def get_bytes(self, num_bytes: int):
        out = bytearray(num_bytes)
        out_offset = 0
        while out_offset != num_bytes:
            out[out_offset] = yield self.deferred_get_byte
            out_offset += 1
        return bytes(out)

    def yield_bytes(self, num_bytes: int):
        def to_yield():
            nonlocal num_bytes
            for chunk in self.yield_bytes_up_to(num_bytes):
                num_bytes -= len(chunk)
                yield chunk

        yield_bytes_up_to = DeferredYielder(can_proceed = self.has_byte, to_yield = to_yield, num_from_cache = lambda: (0, 0), return_value=lambda: None)
        while num_bytes:
            yield yield_bytes_up_to

    def via_cache(self, bytes_iter):
        for chunk in bytes_iter:
            chunk_start = max(len(chunk) - self.cache_size, 0)
            chunk_end = len(chunk)
            chunk_len = chunk_end - chunk_start
            part_1_start = (cache_start + cache_len) % self.cache_size
            part_1_end = min(part_1_start + chunk_len, self.cache_size)
            part_1_chunk_start = chunk_start
            part_1_chunk_end = chunk_start + (part_1_end - part_1_start)
            part_2_start = 0
            part_2_end = chunk_len - (part_1_end - part_1_start)
            part_2_chunk_start = part_1_chunk_end
            part_2_chunk_end = part_1_chunk_end + (part_2_end - part_2_start)

            cache_len_over_size = max((cache_len + chunk_len) - self.cache_size, 0)
            cache_len = min(self.cache_size, cache_len + chunk_len)
            cache_start = (cache_start + cache_len_over_size) % self.cache_size

            self.cache[part_1_start:part_1_end] = chunk[part_1_chunk_start:part_1_chunk_end]
            self.cache[part_2_start:part_2_end] = chunk[part_2_chunk_start:part_2_chunk_end]
            yield chunk
        

    def from_cache(self, dist: int, length: int):
        if dist > self.cache_len:
            raise Exception('Searching backwards too far', dist, len(self.cache))

        available = dist
        part_1_start = (self.cache_start + self.cache_len - dist) % self.cache_size
        part_1_end = min(part_1_start + available, self.cache_size)
        part_2_start = 0
        part_2_end = max(available - (part_1_end - part_1_start), 0)

        while length:
            to_yield = self.cache[part_1_start:part_1_end][:length]
            length -= len(to_yield)
            yield to_yield

            to_yield = self.cache[part_2_start:part_2_end][:length]
            length -= len(to_yield)
            yield to_yield

    def run(self, iterable: Iterable[bytes]):
        self.append(iterable)

    
    def yield_exactly(self, bytes_to_yield):
        return DeferredYielder(can_proceed=lambda: True, to_yield=lambda: (bytes_to_yield,), num_from_cache=lambda: (0, 0), return_value=lambda: None)


    def yield_from_cache(self, dist, length):
        return DeferredYielder(can_proceed=lambda: True, to_yield=lambda: (), num_from_cache=lambda: (dist, length), return_value=lambda: None)


    def get_huffman_codes(lengths):

        def yield_codes():
            max_bits = max(lengths)
            bl_count = defaultdict(int, Counter(lengths))
            next_code = {}
            code = 0
            bl_count[0] = 0
            for bits in range(1, max_bits + 1):
                code = (code + bl_count[bits - 1]) << 1;
                next_code[bits] = code

            for value, length in enumerate(lengths):
                if length != 0:
                    next_code[length] += 1
                    yield (length, next_code[length] - 1), value

        return dict(yield_codes())


    def get_huffman_value(self, get_bits, codes):
        length = 0
        code = 0
        while True:
            length += 1
            code = (code << 1) | ord((yield from get_bits(1)))
            try:
                return codes[(length, code)]
            except KeyError:
                continue

    def get_code_length_code_lengths(self, num_length_codes, get_bits):
        result = [0] * num_length_codes
        for i in range(0, num_length_codes):
            result[i] = ord((yield from get_bits(3)))
        return tuple(result)

    def get_code_lengths(self, get_bits, code_length_codes, num_codes):
        result = [0] * num_codes
        i = 0
        previous = None
        while i < num_codes:
            code = yield from self.get_huffman_value(get_bits, code_length_codes)
            if code < 16:
                previous = code
                result[i] = code
                i += 1
            elif code == 16:
                for _ in range(0, 3 + ord((yield from get_bits(2)))):
                    result[i] = previous
                    i += 1
            elif code == 17:
                i += 3 + ord((yield from get_bits(3)))
                previous = 0
            elif code == 18:
                i += 11 + ord((yield from get_bits(7)))
                previous = 0
        return result


    def inflate(self):
        b_final = b'\0'

        while not b_final[0]:
            b_final = yield from self.get_bits(1)
            b_type = yield from self.get_bytes(2)

            if b_type == b'\3':
                raise exceptions.UnsupportedBlockType(b_type)
            
            if b_type == b'\0':
                b_len = int.from_bytes((yield from self.get_bytes(2)), byteorder='little')
                yield from self.get_bytes(2)
                yield from self.yield_bytes(b_len)
                continue
            
            if b_type == b'\1':
                literal_stop_or_length_codes = self.get_huffman_codes(constants.STREAM_INFLATE_LITERAL_STOP_OR_LENGTH_CODE_LENGTHS)
                backwards_dist_codes = self.get_huffman_codes(constants.STREAM_INFLATE_DIST_CODE_LENGTHS)
            
            else:
                num_literal_length_codes = ord((yield from self.get_bits(5))) + 257
                num_dist_codes = ord((yield from self.get_bits(5))) + 1
                num_length_codes = ord((yield from self.get_bits(4))) + 4

                code_length_code_lengths = (yield from self.get_code_length_code_lengths(num_length_codes, self.get_bits)) + ((0,) * (19 - num_length_codes))
                code_length_code_lengths = tuple(
                    v for i, v in
                    sorted(enumerate(code_length_code_lengths), key=lambda x: constants.STREAM_INFLATE_CODE_LENGTHS_ALPHABET[x[0]])
                )
                code_length_codes = self.get_huffman_codes(code_length_code_lengths)

                dynamic_code_lengths = yield from self.get_code_lengths(self.get_bits, code_length_codes, num_literal_length_codes + num_dist_codes)
                dynamic_literal_code_lengths = dynamic_code_lengths[:num_literal_length_codes]
                dynamic_dist_code_lengths = dynamic_code_lengths[num_literal_length_codes:]

                literal_stop_or_length_codes = self.get_huffman_codes(dynamic_literal_code_lengths)
                backwards_dist_codes = self.get_huffman_codes(dynamic_dist_code_lengths)

            while True:
                literal_stop_or_length_code = yield from self.get_huffman_value(self.get_bits, literal_stop_or_length_codes)
                if literal_stop_or_length_code < 256:
                    yield self.yield_exactly(bytes((literal_stop_or_length_code,)))
                elif literal_stop_or_length_code == 256:
                    break
                else:
                    length_extra_bits, length_diff = self.length_extra_bits_diffs[literal_stop_or_length_code - 257]
                    length_extra = int.from_bytes((yield from self.get_bits(length_extra_bits)), byteorder='little')

                    code = yield from self.get_huffman_value(self.get_bits, backwards_dist_codes)
                    dist_extra_bits, dist_diff = self.dist_extra_bits_diffs[code]
                    dist_extra = int.from_bytes((yield from self.get_bits(dist_extra_bits)), byteorder='little')

                    yield self.yield_from_cache(dist=dist_extra + dist_diff, length=length_extra + length_diff)


    def paginate(self, get_bytes_iter, page_size):

        def _paginate(bytes_iter):
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
                page = b''.join(up_to_page_size(page_size))
                if not page:
                    break
                yield page

        def _run(*args, **kwargs):
            yield from _paginate(get_bytes_iter(*args, **kwargs))

        return _run
    
    def get_runner(self, append, via_cache, from_cache, alg):
        is_done = False
        can_proceed, to_yield, num_from_cache, return_value  = None, None, None, None

        def _is_done():
            return is_done

        def _run(new_iterable):
            nonlocal is_done, can_proceed, to_yield, num_from_cache, return_value

            append(new_iterable)

            while True:
                if can_proceed is None:
                    try:
                        can_proceed, to_yield, num_from_cache, return_value = \
                            next(alg) if return_value is None else \
                            alg.send(return_value())
                    except StopIteration:
                        break
                if not can_proceed():
                    return
                yield from via_cache(to_yield())
                yield from via_cache(from_cache(*num_from_cache()))
                can_proceed = None

            is_done = True

        return _run, _is_done

    def __call__(self):
        run, is_done = self.get_runner(
            self.append, 
            self.via_cache, 
            self.from_cache, 
            self.inflate(self.get_bits, self.get_bytes, self.yield_bytes)
        )
        return self.paginate(run, self.chunk_size), is_done, self.num_bytes_unconsumed

        
