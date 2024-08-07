"""
Modified from 
https://github.com/uktrade/stream-unzip/blob/main/stream_unzip.py
"""


import bz2
import itertools
import zlib
from functools import partial
from struct import Struct

from . import errors

from lazyops.imports._pycryptodome import resolve_pycryptodome

resolve_pycryptodome(True)
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA1
from Crypto.Util import Counter
from Crypto.Protocol.KDF import PBKDF2

from .inflate import StreamInflate
from typing import Iterable, Union, Optional, Any, Callable, Dict, List, Tuple, Type


def next_or_truncated_error(it: Iterable[Any]) -> Any:
    """
    Returns the next item or raises a truncated data error.
    """
    try:
        return next(it)
    except StopIteration:
        raise errors.TruncatedDataError from None


class ByteReader:
    def __init__(
        self,
        iterable: Iterable[bytes],
        chunk_size: int = 65536,
        **kwargs,
    ):
        self.iterable = iterable
        self.chunk = b''
        self.offset = 0
        self.offset_from_start = 0
        self.queue = []
        self.chunk_size = chunk_size
        self.iter = iter(self.iterable)

    def next(self) -> bytes:
        """
        Returns the next byte.
        """
        try:
            return self.queue.pop(0)
        except IndexError:
            return (next_or_truncated_error(self.iter), 0)

    def yield_num(self, num: int) -> Iterable[bytes]:
        """
        Yields the next num bytes.
        """
        while num:
            if self.offset == len(self.chunk):
                self.chunk, self.offset = self.next()
            to_yield = min(num, len(self.chunk) - self.offset, self.chunk_size)
            offset = offset + to_yield
            num -= to_yield
            self.offset_from_start += to_yield
            yield self.chunk[offset - to_yield:offset]

    def yield_all(self) -> Iterable[bytes]:
        """
        Generator that yields all bytes.
        """
        try:
            yield from self.yield_num(float('inf'))
        except errors.TruncatedDataError:
            pass

    def get_num(self, num: int) -> bytes:
        """
        Returns the next num bytes.
        """
        return b''.join(self.yield_num(num))

    def return_num_unused(self, num_unused: int) -> None:
        """
        Returns the next num_unused bytes.
        """
        self.offset -= num_unused
        self.offset_from_start -= num_unused

    def return_bytes_unused(self, bytes_unused: bytes):
        """
        Returns the bytes unused.
        """
        self.queue.insert(0, (self.chunk, self.offset))
        self.chunk = bytes_unused
        self.offset = 0
        self.offset_from_start -= len(bytes_unused)
    

    def get_offset_from_start(self) -> int:
        """
        get the offset from start
        """
        return self.offset_from_start


class DecompressorNone:
    """
    Implements a decompressor that does nothing.
    """
    def __init__(self, num_bytes: int = 0, **kwargs):
        self.num_bytes = num_bytes
        self.num_decompressed = 0
        self.num_unused = 0

    def decompress(self, compressed_chunk: bytes) -> bytes:
        """
        Decompresses the data.
        """
        to_yield = min(len(compressed_chunk), self.num_bytes - self.num_decompressed)
        self.num_decompressed += to_yield
        self.num_unused = len(compressed_chunk) - to_yield
        yield compressed_chunk[:to_yield]

    def is_done(self) -> bool:
        """
        Returns whether the decompressor is done.
        """
        return self.num_decompressed == self.num_bytes
    
    def get_num_unused(self) -> int:
        """
        Returns the number of unused bytes.
        """
        return self.num_unused
    

class DecompressorDeflate:

    def __init__(self, chunk_size: int, **kwargs):
        self.chunk_size = chunk_size
        self.decompressor = zlib.decompressobj(wbits=-zlib.MAX_WBITS)


    def decompress_single(self, compressed_chunk: bytes) -> bytes:
        """
        Decompresses a single chunk.
        """
        try:
            return self.decompressor.decompress(compressed_chunk, self.chunk_size)
        except zlib.error as e:
            raise errors.DeflateError() from e

    def decompress(self, compressed_chunk: bytes) -> Iterable[bytes]:
        """
        Returns the decompressed data.
        """
        uncompressed_chunk = self.decompress_single(compressed_chunk)
        if uncompressed_chunk:
            yield uncompressed_chunk

        while self.decompressor.unconsumed_tail and not self.decompressor.eof:
            uncompressed_chunk = self.decompress_single(self.decompressor.unconsumed_tail)
            if uncompressed_chunk:
                yield uncompressed_chunk

    def is_done(self) -> bool:
        """
        Returns whether the decompressor is done.
        """
        return self.decompressor.eof

    def get_num_unused(self) -> int:
        """
        Returns the number of unused bytes.
        """
        return len(self.decompressor.unused_data)


class DecompressorDeflate64:
    """
    Implements a decompressor for the Deflate64 algorithm.
    """
    def __init__(self, chunk_size: int, **kwargs):
        self.chunk_size = chunk_size
        self.decompressor = StreamInflate(chunk_size = self.chunk_size, b64 = True)
        self.uncompressed_chunks, self.is_done, self.num_bytes_unconsumed = self.decompressor()

    def decompress(self, compressed_chunk: bytes) -> Iterable[bytes]:
        """
        Returns the decompressed data.
        """
        yield from self.uncompressed_chunks((compressed_chunk,))

    def get_num_unused(self) -> int:
        """
        Returns the number of unused bytes.
        """
        return self.num_bytes_unconsumed()

class DecompressorBzip2:
    def __init__(self, chunk_size: int, **kwargs):
        self.chunk_size = chunk_size
        self.decompressor = bz2.BZ2Decompressor()
    
    def decompress_single(self, compressed_chunk: bytes) -> bytes:
        """
        Decompresses a single chunk.
        """
        try:
            return self.decompressor.decompress(compressed_chunk, self.chunk_size)
        except OSError as e:
            raise errors.BZ2Error() from e
        

    def decompress(self, compressed_chunk: bytes) -> Iterable[bytes]:
        """
        Returns the decompressed data.
        """
        uncompressed_chunk = self.decompress_single(compressed_chunk)
        if uncompressed_chunk:
            yield uncompressed_chunk

        while self.decompressor.eof:
            uncompressed_chunk = self.decompress_single(b'')
            if not uncompressed_chunk:
                break 
            yield uncompressed_chunk

    def is_done(self) -> bool:
        """
        Returns whether the decompressor is done.
        """
        return self.decompressor.eof
    
    def get_num_unused(self) -> int:
        """
        Returns the number of unused bytes.
        """
        return len(self.decompressor.unused_data)
    
class YieldFile:
    """
    Implements a file-like object that yields data.
    """
    def __init__(
        self, 
        streamer: 'StreamUnzipper',
        **kwargs
    ):
        self.streamer = streamer
        self.byte_reader = self.streamer.byte_reader
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Hook for post initialization.
        """
        (
            version, 
            flags, 
            compression_raw, 
            self.mod_time, 
            mod_date, 
            self.crc_32_expected, 
            compressed_size_raw, 
            uncompressed_size_raw, 
            file_name_len, 
            extra_field_len
        ) = self.streamer.local_file_header_struct.unpack(
            self.byte_reader.get_num(
                self.streamer.local_file_header_struct.size
            )
        )

        flag_bits = tuple(self.get_flag_bits(flags))
        if (
            flag_bits[4]      # Enhanced deflating
            or flag_bits[5]   # Compressed patched
            or flag_bits[6]   # Strong encrypted
            or flag_bits[13]  # Masked header values
        ):
            raise errors.UnsupportedFlagsError(flag_bits)

        self.file_name = self.byte_reader.get_num(file_name_len)
        extra = dict(self.parse_extra(self.byte_reader.get_num(extra_field_len)))

        is_weak_encrypted = flag_bits[0] and compression_raw != 99
        is_aes_encrypted = flag_bits[0] and compression_raw == 99
        aes_extra = self.get_extra_value(extra, is_aes_encrypted, self.streamer.aes_extra_signature, errors.MissingAESExtraError, 7, errors.TruncatedAESExtraError)
        is_aes_2_encrypted = is_aes_encrypted and aes_extra[:2] == b'\x02\x00'

        if is_weak_encrypted and self.streamer.password is None:
            raise errors.MissingZipCryptoPasswordError()

        if is_aes_encrypted and self.streamer.password is None:
            raise errors.MissingAESPasswordError()

        compression = \
                unsigned_short.unpack(aes_extra[5:7])[0] if is_aes_encrypted else \
                compression_raw

        if compression not in (0, 8, 9, 12):
            raise errors.UnsupportedCompressionTypeError(compression)

        has_data_descriptor = flag_bits[3]
        might_be_zip64 = compressed_size_raw == self.streamer.zip64_compressed_size and uncompressed_size_raw == self.streamer.zip64_compressed_size
        zip64_extra = self.get_extra_value(extra, might_be_zip64, self.streamer.zip64_size_signature, False, 16, errors.TruncatedZip64ExtraError)
        is_sure_zip64 = bool(zip64_extra)

        if not self.streamer.allow_zip64 and is_sure_zip64:
            raise errors.UnsupportedZip64Error()

        self.compressed_size = \
                None if has_data_descriptor and compression in (8, 9, 12) else \
                unsigned_long_long.unpack(zip64_extra[8:16])[0] if is_sure_zip64 else \
                compressed_size_raw

        self.uncompressed_size = \
                None if has_data_descriptor and compression in (8, 9, 12) else \
                unsigned_long_long.unpack(zip64_extra[:8])[0] if is_sure_zip64 else \
                uncompressed_size_raw

        self.decompressor = \
                DecompressorNone(self.uncompressed_size) if compression == 0 else \
                DecompressorDeflate(self.streamer.chunk_size) if compression == 8 else \
                DecompressorDeflate64(self.streamer.chunk_size) if compression == 9 else \
                DecompressorBzip2(self.streamer.chunk_size)

        decompressed_bytes = \
                self.decrypt_weak_decompress(yield_all(), *self.decompressor) if is_weak_encrypted else \
                self.decrypt_aes_decompress(yield_all(), *decompressor, key_length_raw=aes_extra[4]) if is_aes_encrypted else \
                self.decrypt_none_decompress(yield_all(), *decompressor)

        counted_decompressed_bytes, get_compressed_size, get_crc_32_actual, get_uncompressed_size = self.read_data_and_count_and_crc32(decompressed_bytes)

        self.checked_bytes = \
                self.checked_from_data_descriptor(counted_decompressed_bytes, is_sure_zip64, is_aes_2_encrypted, get_crc_32_actual, get_compressed_size, get_uncompressed_size) if has_data_descriptor else \
                self.checked_from_local_header(counted_decompressed_bytes, is_aes_2_encrypted, get_crc_32_actual, get_compressed_size, get_uncompressed_size)
            
    
    def get_flag_bits(self, flags: bytes) -> Iterable[int]:
        """
        Returns the flag bits.
        """
        for b, i in itertools.product(flags, range(8)):
            yield (b >> i) & 1


    def parse_extra(self, extra: bytes) -> Dict[str, bytes]:
        """
        Returns the parsed extra data.
        """
        extra_offset = 0
        while extra_offset <= len(extra) - 4:
            extra_signature = extra[extra_offset:extra_offset+2]
            extra_offset += 2
            extra_data_size, = unsigned_short.unpack(extra[extra_offset:extra_offset+2])
            extra_offset += 2
            extra_data = extra[extra_offset:extra_offset+extra_data_size]
            extra_offset += extra_data_size
            yield (extra_signature, extra_data)


    def get_extra_value(
        self,
        extra, 
        if_true, 
        signature, 
        exception_if_missing, 
        min_length, 
        exception_if_too_short
    ):
        """
        Returns the extra value.
        """
        value = None

        if if_true:
            try:
                value = extra[signature]
            except KeyError as e:
                if exception_if_missing:
                    raise exception_if_missing() from e
            else:
                if len(value) < min_length:
                    raise exception_if_too_short()

        return value

    def decrypt_weak_decompress(self, chunks, decompress, is_done, num_unused) -> Iterable[bytes]:
        """
        Decrypts the weak decompress.
        """
        key_0 = 305419896
        key_1 = 591751049
        key_2 = 878082192
        crc32 = zlib.crc32
        bytes_c = bytes

        def update_keys(byte):
            nonlocal key_0, key_1, key_2
            key_0 = ~crc32(bytes_c((byte,)), ~key_0) & 0xFFFFFFFF
            key_1 = (key_1 + (key_0 & 0xFF)) & 0xFFFFFFFF
            key_1 = ((key_1 * 134775813) + 1) & 0xFFFFFFFF
            key_2 = ~crc32(bytes_c((key_1 >> 24,)), ~key_2) & 0xFFFFFFFF

        def decrypt(chunk):
            chunk = bytearray(chunk)
            for i, byte in enumerate(chunk):
                temp = key_2 | 2
                byte ^= ((temp * (temp ^ 1)) >> 8) & 0xFF
                update_keys(byte)
                chunk[i] = byte
            return bytes(chunk)

        for byte in self.streamer.password:
            update_keys(byte)

        encryption_header = decrypt(self.byte_reader.get_num(12))
        check_password_byte = \
            (mod_time >> 8) if has_data_descriptor else \
            (crc_32_expected >> 24)

        if encryption_header[11] != check_password_byte:
            raise IncorrectZipCryptoPasswordError()

        while not is_done():
            yield from decompress(decrypt(next_or_truncated_error(chunks)))

        self.byte_reader.return_num_unused(num_unused())

    def decrypt_aes_decompress(self, chunks, decompress, is_done, num_unused, key_length_raw):
        try:
            key_length, salt_length = {1: (16, 8), 2: (24, 12), 3: (32, 16)}[key_length_raw]
        except KeyError:
            raise errors.InvalidAESKeyLengthError(key_length_raw)

        salt = self.byte_reader.get_num(salt_length)
        password_verification_length = 2

        keys = PBKDF2(self.streamer.password, salt, 2 * key_length + password_verification_length, 1000)
        if keys[-password_verification_length:] != self.byte_reader.get_num(password_verification_length):
            raise errors.IncorrectAESPasswordError()

        decrypter = AES.new(
            keys[:key_length], AES.MODE_CTR,
            counter=Counter.new(nbits=128, little_endian=True)
        )
        hmac = HMAC.new(keys[key_length:key_length*2], digestmod=SHA1)

        while not is_done():
            chunk = next_or_truncated_error(chunks)
            yield from decompress(decrypter.decrypt(chunk))
            hmac.update(chunk[:len(chunk) - num_unused()])

        self.byte_reader.return_num_unused(num_unused())

        if self.byte_reader.get_num(10) != hmac.digest()[:10]:
            raise errors.HMACIntegrityError()

    def decrypt_none_decompress(self, chunks, decompress, is_done, num_unused):
        while not is_done():
            yield from decompress(next_or_truncated_error(chunks))

        self.byte_reader.return_num_unused(num_unused())

    def read_data_and_count_and_crc32(self, chunks):
        offset_1 = None
        offset_2 = None
        crc_32_actual = zlib.crc32(b'')
        l = 0

        def _iter():
            nonlocal offset_1, offset_2, crc_32_actual, l

            offset_1 = self.byte_reader.get_offset_from_start()
            for chunk in chunks:
                crc_32_actual = zlib.crc32(chunk, crc_32_actual)
                l += len(chunk)
                yield chunk
            offset_2 = self.byte_reader.get_offset_from_start()

        return _iter(), lambda: offset_2 - offset_1, lambda: crc_32_actual, lambda: l

    def checked_from_local_header(self, chunks, is_aes_2_encrypted, get_crc_32, get_compressed_size, get_uncompressed_size):
        yield from chunks

        crc_32_data = get_crc_32()
        compressed_size_data = get_compressed_size()
        uncompressed_size_data = get_uncompressed_size()

        if not is_aes_2_encrypted and self.crc_32_expected != crc_32_data:
            raise errors.CRC32IntegrityError()

        if compressed_size_data != self.compressed_size:
            raise errors.CompressedSizeIntegrityError()

        if uncompressed_size_data != self.uncompressed_size:
            raise errors.UncompressedSizeIntegrityError()

    def checked_from_data_descriptor(self, chunks, is_sure_zip64, is_aes_2_encrypted, get_crc_32, get_compressed_size, get_uncompressed_size):
        # The format of the data descriptor is unfortunately not known with absolute certainty in all cases
        # so we we use a heuristic to detect it - using the known crc32 value, compressed size, uncompressed
        # size of the data, and possible signature of the next section in the stream. There are 4 possible
        # formats, and we choose the longest one that matches
        #
        # Strongly inspired by Mark Adler's unzip - see his reasoning for this at
        # https://github.com/madler/unzip/commit/af0d07f95809653b669d88aa0f424c6d5aa48ba0

        yield from chunks

        crc_32_data = get_crc_32()
        compressed_size_data = get_compressed_size()
        uncompressed_size_data = get_uncompressed_size()
        best_matches = (False, False, False, False, False)
        must_treat_as_zip64 = is_sure_zip64 or compressed_size_data > 0xFFFFFFFF or uncompressed_size_data > 0xFFFFFFFF

        checks = ((
            (dd_struct_64_with_sig, dd_optional_signature),
            (dd_struct_64, b''),
        ) if allow_zip64 else ()) + ((
            (dd_struct_32_with_sig, dd_optional_signature),
            (dd_struct_32, b''),
        ) if not must_treat_as_zip64 else ())

        dd = get_num(checks[0][0].size)

        for dd_struct, expected_signature in checks:
            signature_dd, crc_32_dd, compressed_size_dd, uncompressed_size_dd, next_signature = dd_struct.unpack(dd[:dd_struct.size])
            matches = (
                signature_dd == expected_signature,
                is_aes_2_encrypted or crc_32_dd == crc_32_data,
                compressed_size_dd == compressed_size_data,
                uncompressed_size_dd == uncompressed_size_data,
                next_signature in (local_file_header_signature, central_directory_signature),
            )
            best_matches = max(best_matches, matches, key=lambda t: t.count(True))

            if best_matches == (True, True, True, True, True):
                break

        if not best_matches[0]:
            raise UnexpectedSignatureError()

        if not best_matches[1]:
            raise CRC32IntegrityError()

        if not best_matches[2]:
            raise CompressedSizeIntegrityError()

        if not best_matches[3]:
            raise UncompressedSizeIntegrityError()

        if not best_matches[4]:
            raise UnexpectedSignatureError(next_signature)

        return_bytes_unused(dd[dd_struct.size - 4:])  # 4 is the length of next signature we have already taken

    
    

class StreamUnzipper:
    def __init__(
        self,
        stream: Iterable[bytes],
        password: Optional[str] = None,
        chunk_size: int = 65536,
        allow_zip64: bool = True,
        **kwargs,
    ):
        self.stream = stream
        self.chunk_size = chunk_size
        self.allow_zip64 = allow_zip64
        self.password = password
        self.post_init(**kwargs)

    def post_init(self, **kwargs):
        """
        Post initialization hook.
        """
        self.post_init_constants(**kwargs)

    def post_init_constants(self, **kwargs):
        """
        Post initialization hook for constants.
        """
        self.local_file_header_signature = b'PK\x03\x04'
        self.local_file_header_struct = Struct('<H2sHHHIIIHH')
        self.zip64_compressed_size = 0xFFFFFFFF
        self.zip64_size_signature = b'\x01\x00'
        self.aes_extra_signature = b'\x01\x99'
        self.central_directory_signature = b'PK\x01\x02'
        self.unsigned_short = Struct('<H')
        self.unsigned_long_long = Struct('<Q')

        self.dd_optional_signature = b'PK\x07\x08'
        self.dd_struct_32 = Struct('<0sIII4s')
        self.dd_struct_32_with_sig = Struct('<4sIII4s')
        self.dd_struct_64 = Struct('<0sIQQ4s')
        self.dd_struct_64_with_sig = Struct('<4sIQQ4s')

    def post_init_objects(self, **kwargs):
        """
        Post initialization hook for objects.
        """
        self.byte_reader = ByteReader(self.stream, chunk_size = self.chunk_size)
        self.yield_file = YieldFile(self.byte_reader)

        # self.stream_inflater = StreamInflate(self.stream_reader, chunk_size = self.chunk_size)
        # self.stream_decrypter = self.get_decrypter()

    def get_byte_reader(self) -> ByteReader:
        """
        Returns the byte reader.
        """
        return ByteReader(self.stream, chunk_size = self.chunk_size)