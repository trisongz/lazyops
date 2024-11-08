from __future__ import annotations

import contextlib
from typing import Optional, Dict, Any, Union, List, TYPE_CHECKING

with contextlib.suppress(ImportError):
    import s3fs
    from s3fs.errors import translate_boto_error
    from botocore.exceptions import ClientError
    from s3fs.core import _error_wrapper, sync_wrapper


if TYPE_CHECKING:
    from s3transfer.manager import TransferManager

class MinioFileSystem(s3fs.S3FileSystem):
    """
    Access Minio as if it were a file system.

    This exposes a filesystem-like API (ls, cp, open, etc.) on top of S3
    storage.

    Provide credentials either explicitly (``key=``, ``secret=``) or depend
    on boto's credential methods. See botocore documentation for more
    information. If no credentials are available, use ``anon=True``.

    Parameters
    ----------
    anon : bool (False)
        Whether to use anonymous connection (public buckets only). If False,
        uses the key/secret given, or boto's credential resolver (client_kwargs,
        environment, variables, config files, EC2 IAM server, in that order)
    endpoint_url : string (None)
        Use this endpoint_url, if specified. Needed for connecting to non-AWS
        S3 buckets. Takes precedence over `endpoint_url` in client_kwargs.
    key : string (None)
        If not anonymous, use this access key ID, if specified. Takes precedence
        over `aws_access_key_id` in client_kwargs.
    secret : string (None)
        If not anonymous, use this secret access key, if specified. Takes
        precedence over `aws_secret_access_key` in client_kwargs.
    token : string (None)
        If not anonymous, use this security token, if specified
    use_ssl : bool (True)
        Whether to use SSL in connections to S3; may be faster without, but
        insecure. If ``use_ssl`` is also set in ``client_kwargs``,
        the value set in ``client_kwargs`` will take priority.
    s3_additional_kwargs : dict of parameters that are used when calling s3 api
        methods. Typically used for things like "ServerSideEncryption".
    client_kwargs : dict of parameters for the botocore client
    requester_pays : bool (False)
        If RequesterPays buckets are supported.
    default_block_size: int (None)
        If given, the default block size value used for ``open()``, if no
        specific value is given at all time. The built-in default is 5MB.
    default_fill_cache : Bool (True)
        Whether to use cache filling with open by default. Refer to
        ``S3File.open``.
    default_cache_type : string ("readahead")
        If given, the default cache_type value used for ``open()``. Set to "none"
        if no caching is desired. See fsspec's documentation for other available
        cache_type values. Default cache_type is "readahead".
    version_aware : bool (False)
        Whether to support bucket versioning.  If enable this will require the
        user to have the necessary IAM permissions for dealing with versioned
        objects. Note that in the event that you only need to work with the
        latest version of objects in a versioned bucket, and do not need the
        VersionId for those objects, you should set ``version_aware`` to False
        for performance reasons. When set to True, filesystem instances will
        use the S3 ListObjectVersions API call to list directory contents,
        which requires listing all historical object versions.
    cache_regions : bool (False)
        Whether to cache bucket regions or not. Whenever a new bucket is used,
        it will first find out which region it belongs and then use the client
        for that region.
    asynchronous :  bool (False)
        Whether this instance is to be used from inside coroutines.
    config_kwargs : dict of parameters passed to ``botocore.client.Config``
    kwargs : other parameters for core session.
    session : aiobotocore AioSession object to be used for all connections.
         This session will be used inplace of creating a new session inside S3FileSystem.
         For example: aiobotocore.session.AioSession(profile='test_user')

    The following parameters are passed on to fsspec:

    skip_instance_cache: to control reuse of instances
    use_listings_cache, listings_expiry_time, max_paths: to control reuse of directory listings

    Examples
    --------
    >>> s3 = S3FileSystem(anon=False)  # doctest: +SKIP
    >>> s3.ls('my-bucket/')  # doctest: +SKIP
    ['my-file.txt']

    >>> with s3.open('my-bucket/my-file.txt', mode='rb') as f:  # doctest: +SKIP
    ...     print(f.read())  # doctest: +SKIP
    b'Hello, world!'
    """

    