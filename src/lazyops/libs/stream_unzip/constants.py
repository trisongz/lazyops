from struct import Struct

STREAM_INFLATE_CHUNK_SIZE = 65536
STREAM_INFLATE_CACHE_SIZE = 32768

STREAM_INFLATE_LENGTH_EXTRA_BITS_DIFFS = (
    (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
    (1, 11), (1, 13), (1, 15), (1, 17),
    (2, 19), (2, 23), (2, 27), (2, 31),
    (3, 35), (3, 43), (3, 51), (3, 59),
    (4, 67), (4, 83), (4, 99), (4, 115),
    (5, 131), (5, 163), (5, 195), (5, 227),
    (0, 258),
)
STREAM_INFLATE_DIST_EXTRA_BITS_DIFFS = (
    (0, 1), (0, 2), (0, 3), (0, 4),
    (1, 5), (1, 7), (2, 9), (2, 13),
    (3, 17), (3, 25), (4, 33), (4, 49),
    (5, 65), (5, 97), (6, 129), (6, 193),
    (7, 257), (7, 385), (8, 513), (8, 769),
    (9, 1025), (9, 1537), (10, 2049), (10, 3073),
    (11, 4097), (11, 6145), (12, 8193), (12, 12289),
    (13, 16385), (13, 24577),
)

# For 

STREAM_INFLATE64_CHUNK_SIZE = 65536
STREAM_INFLATE64_CACHE_SIZE = 65536

STREAM_INFLATE64_LENGTH_EXTRA_BITS_DIFFS = (
    (0, 3), (0, 4), (0, 5), (0, 6), (0, 7), (0, 8), (0, 9), (0, 10),
    (1, 11), (1, 13), (1, 15), (1, 17),
    (2, 19), (2, 23), (2, 27), (2, 31),
    (3, 35), (3, 43), (3, 51), (3, 59),
    (4, 67), (4, 83), (4, 99), (4, 115),
    (5, 131), (5, 163), (5, 195), (5, 227),
    (16, 3),
)
STREAM_INFLATE64_DIST_EXTRA_BITS_DIFFS = (
    (0, 1), (0, 2), (0, 3), (0, 4),
    (1, 5), (1, 7), (2, 9), (2, 13),
    (3, 17), (3, 25), (4, 33), (4, 49),
    (5, 65), (5, 97), (6, 129), (6, 193),
    (7, 257), (7, 385), (8, 513), (8, 769),
    (9, 1025), (9, 1537), (10, 2049), (10, 3073),
    (11, 4097), (11, 6145), (12, 8193), (12, 12289),
    (13, 16385), (13, 24577), (14, 32769), (14, 49153),
)


STREAM_INFLATE_LITERAL_STOP_OR_LENGTH_CODE_LENGTHS = \
    (8,) * 144 + \
    (9,) * 112 + \
    (7,) * 24 + \
    (8,) * 8

STREAM_INFLATE_DIST_CODE_LENGTHS = \
    (5,) * 32

STREAM_INFLATE_CODE_LENGTHS_ALPHABET = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)

STREAM_INFLATE_YIELDER_VARS = (
    'can_proceed',
    'to_yield',
    'num_from_cache',
    'return_value',
)


LOCAL_FILE_HEADER_SIGNATURE = b'PK\x03\x04'
LOCAL_FILE_HEADER_STRUCT = Struct('<H2sHHHIIIHH')
ZIP64_COMPRESSED_SIZE = 0xFFFFFFFF
ZIP64_SIZE_SIGNATURE = b'\x01\x00'
AES_EXTRA_SIGNATURE = b'\x01\x99'
CENTRAL_DIRECTORY_SIGNATURE = b'PK\x01\x02'
UNSIGNED_SHORT = Struct('<H')
UNSIGNED_LONG_LONG = Struct('<Q')

DD_OPTIONAL_SIGNATURE = b'PK\x07\x08'
DD_STRUCT_32 = Struct('<0sIII4s')
DD_STRUCT_32_WITH_SIG = Struct('<4sIII4s')
DD_STRUCT_64 = Struct('<0sIQQ4s')
DD_STRUCT_64_WITH_SIG = Struct('<4sIQQ4s')
