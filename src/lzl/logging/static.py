

DEFAULT_STATUS_COLORS = {
    'debug': '<fg #D9ED92>',
    'info': '<fg #34A0A4>',
    'success': '<fg #52B69A>',
    'warning': '<fg #F48C06>',
    'error': '<fg #DC2F02>',
    'critical': '<fg #9D0208>',
}
    

QUEUE_STATUS_COLORS = {
    'new': '<fg #D9ED92>',
    'deferred': '<fg #B5E48C>',
    'queued': '<fg #99D98C>',
    'active': '<fg #76C893>',
    'complete': '<fg #52B69A>',

    # Error Colors
    'aborted': '<fg #FFBA08>',
    'failed': '<fg #9D0208>',

    # Other Colors
    'enqueue': '<fg #168AAD>',
    'finish': '<fg #52B69A>',
    'completed': '<fg #52B69A>',
    'error': '<fg #DC2F02>',
    'abort': '<fg #DC2F02>',

    'retry': '<fg #F48C06>',
    'scheduled': '<fg #34A0A4>',
    'reschedule': '<fg #34A0A4>',
    'startup': '<fg #168AAD>',
    'shutdown': '<fg #6A040F>',
    'process': '<fg #184E77>',
    'sweep': '<fg #B5E48C>',
    'stats': '<fg #B5E48C>',
    'dequeue': '<fg #168AAD>',

    'stuck': '<fg #DC2F02>',
}

STATUS_COLOR = QUEUE_STATUS_COLORS
FALLBACK_STATUS_COLOR = '<fg #99D98C>'

# DEFAULT_FUNCTION_COLOR = '<fg #457b9d>'
DEFAULT_FUNCTION_COLOR = '<fg #219ebc>'
DEFAULT_CLASS_COLOR = '<fg #a8dadc>'
RESET_COLOR = '\x1b[0m'

LOGLEVEL_MAPPING = {
    50: 'CRITICAL',
    40: 'ERROR',
    30: 'WARNING',
    20: 'INFO',
    19: 'DEV',
    10: 'DEBUG',
    5: 'CRITICAL',
    4: 'ERROR',
    3: 'WARNING',
    2: 'INFO',
    1: 'DEBUG',
    0: 'NOTSET',
}

REVERSE_LOGLEVEL_MAPPING = {v: k for k, v in LOGLEVEL_MAPPING.items()}
COLORED_MESSAGE_MAP = {
    '|bld|': '<bold>',
    '|reset|': '</>',
    '|eee|': '</></></>',
    '|em|': '<bold>',
    '|ee|': '</></>',
    '|lr|': '<light-red>',
    '|lb|': '<light-blue>',
    '|lm|': '<light-magenta>',
    '|lc|': '<light-cyan>',
    '|lw|': '<light-white>',
    # '|gr|': '<gray>',
    # '|gr|': "\033[90m",
    '|gr|': '<fg #808080>',
    '|lk|': '<light-black>',
    '|br|': "\x1b[31;1m", # Bold Red
    '|k|': '<black>',
    '|r|': '<red>',
    '|m|': '<magenta>',
    '|c|': '<cyan>',
    '|u|': '<underline>',
    '|i|': '<italic>',
    '|s|': '<strike>',
    '|e|': '</>',
    '|g|': '<green>',
    '|y|': '<yellow>',
    '|b|': '<blue>',
    '|w|': '<white>',
}
