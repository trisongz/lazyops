import time
from collections import OrderedDict, UserDict
from lazyops.utils.times import Timer
from lazyops.utils import logger

def test_native():
    logger.info('--- NATIVE ---')
    t = Timer()
    time.sleep(5)
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot

    time.sleep(5)
    logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    time.sleep(1)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')
    

def test_no_ckpt():

    logger.info('--- NO CKPT ---')

    t = Timer(auto_checkpoint=False)
    time.sleep(5)
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot

    time.sleep(5)
    logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    time.sleep(1)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')


def test_previous_duration():

    logger.info('-- Previous Duration ---')

    start_value = 240535.0
    t = Timer(start = start_value)
    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot
    logger.info('---')

    time.sleep(15)
    # logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    logger.info('---')
    time.sleep(5)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')

def test_previous_duration_short():
    start_value = 240535.0

    logger.info('-- Previous Duration (Short 0) ---')
    t = Timer(start = start_value, format_short= 0)
    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot
    logger.info('---')

    time.sleep(15)
    # logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    logger.info('---')
    time.sleep(5)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')

    logger.info('-- Previous Duration (Short 1) ---')
    t = Timer(start = start_value, format_short= 1)
    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot
    logger.info('---')

    time.sleep(15)
    # logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    logger.info('---')
    time.sleep(5)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')

    logger.info('-- Previous Duration (Short 2) ---')
    t = Timer(start = start_value, format_short= 2)
    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot
    logger.info('---')

    time.sleep(15)
    # logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    logger.info('---')
    time.sleep(5)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')

    logger.info('-- Previous Duration (Short 3) ---')

    t = Timer(start = start_value, format_short= 3)
    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')
    logger.info(f'Total: {t}')
    logger.info(f'Duration: {t.duration_s}', ) # Snapshot
    logger.info('---')

    time.sleep(15)
    # logger.info(f'Total: {t}')
    logger.info(f'Total: {t.total_s}') # Snapshot
    logger.info(f'Elapsed (Pre): {t.elapsed_s}')
    logger.info(f'Duration: {t.duration_s}')
    logger.info('---')
    time.sleep(5)
    logger.info(f'Elapsed (Post): {t.elapsed_s}')
    logger.info(f'Avg: {t.average_s}')
    logger.info(f'Total: {t}')


def test_op():

    import json
    start_value = 240535.0

    logger.info('-- Testing Operations ---')
    t = Timer(start = start_value)

    logger.info(f'Starting from: {t.pformat(start_value)}')
    logger.info(f'Start: {t.start}')

    t += 10.0
    logger.info(f'Add Total: {t}')

    t -= 5.0
    logger.info(f'Sub Total: {t}')

    t *= 2.0
    logger.info(f'Multiply Total: {t}')

    t /= 2.0
    logger.info(f'Divide Total: {t}')

    is_gt = t > start_value + 100.0
    logger.info(f'is_gt: {is_gt}')

    is_lt = t < start_value + 100.0
    logger.info(f'is_lt: {is_lt}')

    is_eq = t == start_value
    logger.info(f'is_eq: {is_eq}')
    # d = UserDict(t.dict())
    d = t.dict()
    # print(dir(d))
    print(t.__dict__)
    # from pydantic import ByteSize

    # b = ByteSize(1000)
    logger.info(f'Json Dump: {json.dumps(t)}')
    # logger.info(f'Json Dump: {json.dumps(b)}')



def run_tests():
    # test_native()
    # test_no_ckpt()
    # test_previous_duration()
    # test_previous_duration_short()
    test_op()

if __name__ == '__main__':
    run_tests()