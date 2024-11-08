import re

bucket_format_list = [
    re.compile(
        r"^(?P<bucket>arn:(aws).*:r2:[a-z\-0-9]*:[0-9]{12}:accesspoint[:/][^/]+)/?"
        r"(?P<key>.*)$"
    ),
    re.compile(
        r"^(?P<bucket>arn:(aws).*:s3:[a-z\-0-9]*:[0-9]{12}:accesspoint[:/][^/]+)/?"
        r"(?P<key>.*)$"
    ),
    re.compile(
        r"^(?P<bucket>arn:(aws).*:s3-outposts:[a-z\-0-9]+:[0-9]{12}:outpost[/:]"
        r"[a-zA-Z0-9\-]{1,63}[/:](bucket|accesspoint)[/:][a-zA-Z0-9\-]{1,63})[/:]?(?P<key>.*)$"
    ),
    re.compile(
        r"^(?P<bucket>arn:(aws).*:s3-outposts:[a-z\-0-9]+:[0-9]{12}:outpost[/:]"
        r"[a-zA-Z0-9\-]{1,63}[/:]bucket[/:]"
        r"[a-zA-Z0-9\-]{1,63})[/:]?(?P<key>.*)$"
    ),
    re.compile(
        r"^(?P<bucket>arn:(aws).*:s3-object-lambda:[a-z\-0-9]+:[0-9]{12}:"
        r"accesspoint[/:][a-zA-Z0-9\-]{1,63})[/:]?(?P<key>.*)$"
    ),
]