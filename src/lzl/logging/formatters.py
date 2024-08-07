from __future__ import annotations


from enum import Enum
from .static import DEFAULT_CLASS_COLOR, DEFAULT_FUNCTION_COLOR, RESET_COLOR, QUEUE_STATUS_COLORS, FALLBACK_STATUS_COLOR
from typing import Dict, Any, Union


class LoggerFormatter:

    max_extra_lengths: Dict[str, int] = {}

    @classmethod
    def get_extra_length(cls, key: str, value: str) -> int:
        """
        Returns the max length of an extra key
        """
        if key not in cls.max_extra_lengths:
            cls.max_extra_lengths[key] = len(key)
        if len(value) > cls.max_extra_lengths[key]:
            cls.max_extra_lengths[key] = len(value)
        return cls.max_extra_lengths[key]

    @classmethod
    def queue_logger_formatter(cls, record: Dict[str, Union[Dict[str, Any], Any]]) -> str:
        """
        Formats the log message for the queue.
        """
        _extra: Dict[str, Union[Dict[str, Any], Any]] = record.get('extra', {})
        if not record['extra'].get('worker_name'):
            record['extra']['worker_name'] = ''
        
        status = _extra.get('status')
        kind: str = _extra.get('kind')
        if status and isinstance(status, Enum): status = status.name
        
        kind_color = QUEUE_STATUS_COLORS.get(kind.lower(), FALLBACK_STATUS_COLOR)
        if '<' not in kind_color: kind_color = f'<{kind_color}>'
        extra = kind_color + '{extra[kind]}</>:'
        if _extra.get('queue_name'):
            queue_name_length = cls.get_extra_length('queue_name', _extra['queue_name'])
            extra += '<b><fg #006d77>{extra[queue_name]:<' + str(queue_name_length) + '}</></>:'
        if _extra.get('worker_name'):
            worker_name_length = cls.get_extra_length('worker_name', _extra['worker_name'])
            extra += '<fg #83c5be>{extra[worker_name]:<' + str(worker_name_length) + '}</>:'
        # extra += '<fg #83c5be>{extra[worker_name]}</>:<b><fg #006d77>{extra[queue_name]:<18}</></>:'
        if _extra.get('job_id'):
            extra += '<fg #005f73>{extra[job_id]}</>'
        if status:
            status_color = QUEUE_STATUS_COLORS.get(status.lower(), FALLBACK_STATUS_COLOR)
            if '<' not in status_color: status_color = f'<{status_color}>'
            extra += f':{status_color}' + '{extra[status]}</>: '
        # extra += RESET_COLOR
        # print(extra)
        return extra


    @classmethod
    def default_formatter(cls, record: Dict[str, Union[Dict[str, Any], Any]]) -> str:
        """
        To add a custom format for a module, add another `elif` clause with code to determine `extra` and `level`.

        From that module and all submodules, call logger with `logger.bind(foo='bar').info(msg)`.
        Then you can access it with `record['extra'].get('foo')`.
        """        
        _extra = record.get('extra', {})
        if _extra.get('module_name'):
            extra = DEFAULT_CLASS_COLOR + '{extra[module_name]}</>:' + DEFAULT_FUNCTION_COLOR + '{function}</>: '
        else:
            extra = DEFAULT_CLASS_COLOR + '{name}</>:' + DEFAULT_FUNCTION_COLOR + '{function}</>: '
        if _extra.get('worker_name') or _extra.get('queue_name'):
            extra = cls.queue_logger_formatter(record)
        
        if 'result=tensor([' not in str(record['message']):
            return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: " \
                       + extra + "<level>{message}</level>" + RESET_COLOR + "\n"
        
        msg = str(record['message'])[:100].replace('{', '(').replace('}', ')')
        return "<level>{level: <8}</> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</>: "\
                   + extra + "<level>" + msg + f"</level>{RESET_COLOR}\n"

