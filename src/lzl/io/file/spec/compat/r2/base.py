from __future__ import annotations

import io
import anyio
import asyncio
import contextlib
import errno
from typing import Optional, Dict, Any, Union, List, TYPE_CHECKING

with contextlib.suppress(ImportError):
    import s3fs
    from fsspec.asyn import AbstractAsyncStreamedFile, sync, get_loop
    from s3fs.core import _inner_fetch, _fetch_range as _sync_fetch_range
    from s3fs.utils import FileExpired

if TYPE_CHECKING:
    from .filesys import R2FileSystem

from .utils import _log


"""
Base R2 File
"""

class R2File(s3fs.S3File):
    fs: 'R2FileSystem' = None
    buffer: io.BytesIO = None

    def _call_s3(self, method, *kwarglist, **kwargs):
        """
        Filter out ACL for methods that we know will fail
        """
        # if method in ["create_multipart_upload", "put_object", "put_object_acl"]:
        acl = kwargs.pop("ACL", None)
        _log(f'calling method: {method}')
        return self.fs.call_s3(method, self.s3_additional_kwargs, *kwarglist, **kwargs)


    def _upload_chunk(self, final=False):
        bucket, key, _ = self.fs.split_path(self.path)
        _log(
            f"Upload for {self}, final={final}, loc={self.loc}, buffer loc={self.buffer.tell()}"
        )
        if (
            self.autocommit
            and not self.append_block
            and final
            and self.tell() < self.blocksize
        ):
            # only happens when closing small file, use on-shot PUT
            data1 = False
        else:
            self.buffer.seek(0)
            (data0, data1) = (None, self.buffer.read(self.blocksize))

        while data1:
            (data0, data1) = (data1, self.buffer.read(self.blocksize))
            data1_size = len(data1)

            if 0 < data1_size < self.blocksize:
                remainder = data0 + data1
                remainder_size = self.blocksize + data1_size

                if remainder_size <= self.part_max:
                    (data0, data1) = (remainder, None)
                else:
                    partition = remainder_size // 2
                    (data0, data1) = (remainder[:partition], remainder[partition:])

            part = len(self.parts) + 1
            _log(f"Upload chunk {self}, {part}, {self.blocksize}/{data1_size}")

            out = self._call_s3(
                "upload_part",
                Bucket=bucket,
                PartNumber=part,
                UploadId=self.mpu["UploadId"],
                Body=data0,
                Key=key,
            )

            self.parts.append({"PartNumber": part, "ETag": out["ETag"]})

        if self.autocommit and final:
            self.commit()
        return not final
    

    def commit(self):
        _log(f"Commit {self}")
        if self.tell() == 0:
            if self.buffer is not None:
                _log(f"Empty file committed {self}")
                self._abort_mpu()
                write_result = self.fs.touch(self.path)
        elif not self.parts:
            if self.buffer is None:
                raise RuntimeError

            _log(f"One-shot upload of {self}: {self.key}")
            self.buffer.seek(0)
            data = self.buffer.read()
            write_result = self._call_s3(
                "put_object",
                Key=self.key,
                Bucket=self.bucket,
                Body=data,
                ACL=self.acl,
                **self.kwargs,
            )
        else:
            part_info = {"Parts": self.parts}
            _log(f"Complete multi-part upload for {self}: {self.key} {part_info}")
            try:
                write_result = self._call_s3(
                    "complete_multipart_upload",
                    Bucket=self.bucket,
                    Key=self.key,
                    UploadId=self.mpu["UploadId"],
                    # Action="mpu-complete",
                    # Parts=part_info["Parts"],
                    MultipartUpload=part_info,

                )
                # self.mpu.complete()
            except Exception as e:
                self._abort_mpu()
                if 'All non-trailing' in str(e):
                    _log(f"Attempting to upload large file {self}", verbose = True)
                    try:
                        self._large_upload()
                    except Exception as e2:
                        _log(f"Failed to upload large file {self}", verbose = True)
                        raise e2
                raise e

        if self.fs.version_aware: self.version_id = write_result.get("VersionId")
        # complex cache invalidation, since file's appearance can cause several
        # directories
        self.buffer = None
        parts = self.path.split("/")
        path = parts[0]
        for p in parts[1:]:
            if path in self.fs.dircache and not [
                True for f in self.fs.dircache[path] if f["name"] == f"{path}/{p}"
            ]: self.fs.invalidate_cache(path)
            path = f"{path}/{p}"

    def write(self, data: Union[bytes, bytearray, memoryview]):
        """
        Write data to buffer.

        Buffer only sent on flush() or if buffer is greater than
        or equal to blocksize.

        Parameters
        ----------
        data: bytes
            Set of bytes to be written.
        """
        if self.mode not in {"wb", "ab"}: raise ValueError("File not in write mode")
        if self.closed: raise ValueError("I/O operation on closed file.")
        if self.forced: raise ValueError("This file has been force-flushed, can only close")
        out = self.buffer.write(data)
        self.loc += out
        if self.buffer.tell() >= self.blocksize: self.flush()
        return out

    def _large_upload(self, callbacks: Optional[List[Any]] = None, **kwargs):
        """
        Handles large file uploads bc multipart upload isnt working.
        """
        bucket, key, _ = self.fs.split_path(self.path)
        _log(f"Large upload for {self}, loc={self.loc}, buffer loc={self.buffer.tell()}")
        self.buffer.seek(0)
        future = self.fs.s3tm.upload(
            self.buffer,
            bucket,
            key,
            subscribers = callbacks
        )
        res = future.result()
        _log(f"Large upload for {self} complete: {res}")
        self.buffer = io.BytesIO()


    def flush(self, force: bool = False):
        """
        Write buffered data to backend store.

        Writes the current buffer, if it is larger than the block-size, or if
        the file is being closed.

        Parameters
        ----------
        force: bool
            When closing, write the last block even if it is smaller than
            blocks are allowed to be. Disallows further writing to this file.
        """

        if self.closed: raise ValueError("Flush on closed file")
        if force and self.forced: raise ValueError("Force flush cannot be called more than once")
        if force: self.forced = True

        # no-op to flush on read-mode
        if self.mode not in {"wb", "ab"}: return

        # Defer write on small block
        if not force and self.buffer.tell() < self.blocksize: return
        
        # if self.buffer.tell() >= self.fs.default_r2_max_size:
        # if self.buffer.tell() >= self.fs.default_r2_block_size:
        #     # Write large file
        #     self._large_upload()
        #     return

        # Write large file
        if self.buffer.tell() >= self.fs.default_r2_large_file_threshold:
            self._large_upload()
            return

        if self.offset is None:
            # Initialize a multipart upload
            self.offset = 0
            try: self._initiate_upload()
            except:  # noqa: E722
                self.closed = True
                raise
        
        if self._upload_chunk(final=force) is not False:
            self.offset += self.buffer.seek(0, 2)
            self.buffer = io.BytesIO()


"""
Async Streamed File
"""

class R2AsyncStreamedFile(R2File, AbstractAsyncStreamedFile):
    fs: 'R2FileSystem' = None

    """
    Note, this shouldn't be called for 
    `rb` mode, since it doesnt work with
    the loops for some reason.
    """

    def __init__(self, fs: 'R2FileSystem', path, mode, encoding: Optional[str], errors: Optional[str], newline: Optional[str], buffering: Optional[int], **kwargs):
        super().__init__(fs, path, mode, **kwargs)
        self.r = None
        self.size = None


    async def _acall_s3(self, method, *kwarglist, **kwargs):
        """
        Filter out ACL for methods that we know will fail
        """
        kwargs.pop("ACL", None)
        _log(f'calling method: {method}')
        return await self.fs._call_s3(method, self.s3_additional_kwargs, *kwarglist, **kwargs)


    async def _initiate_upload(self):
        # only happens when closing small file, use on-shot PUT
        if self.autocommit and not self.append_block and self.tell() < self.blocksize: return
        _log(f"Initiate upload for {self}")
        self.parts = []
        self.mpu = await self._acall_s3(
            "create_multipart_upload",
            Bucket=self.bucket,
            Key=self.key,
            ACL=self.acl,
        )

        if self.append_block:
            # use existing data in key when appending,
            # and block is big enough
            out = await self._acall_s3(
                "upload_part_copy",
                self.s3_additional_kwargs,
                Bucket=self.bucket,
                Key=self.key,
                PartNumber=1,
                UploadId=self.mpu["UploadId"],
                CopySource=self.path,
            )
            self.parts.append({"PartNumber": 1, "ETag": out["CopyPartResult"]["ETag"]})

    async def _upload_chunk(self, final: bool = False):
        bucket, key, _ = self.fs.split_path(self.path)
        _log(f"Upload for {self}, final={final}, loc={self.loc}, buffer loc={self.buffer.tell()}")
        
        # only happens when closing small file, use on-shot PUT
        if (
            self.autocommit
            and not self.append_block
            and final
            and self.tell() < self.blocksize
        ): data1 = False
        else:
            self.buffer.seek(0)
            (data0, data1) = (None, self.buffer.read(self.blocksize))

        while data1:
            (data0, data1) = (data1, self.buffer.read(self.blocksize))
            data1_size = len(data1)

            if 0 < data1_size < self.blocksize:
                remainder = data0 + data1
                remainder_size = self.blocksize + data1_size
                if remainder_size <= self.part_max: (data0, data1) = (remainder, None)
                else:
                    partition = remainder_size // 2
                    (data0, data1) = (remainder[:partition], remainder[partition:])

            part = len(self.parts) + 1
            _log(f"Upload chunk {self}, {part}, {self.blocksize}/{data1_size}")
            out = await self._acall_s3(
                "upload_part",
                Bucket=bucket,
                PartNumber=part,
                UploadId=self.mpu["UploadId"],
                Body=data0,
                Key=key,
            )
            self.parts.append({"PartNumber": part, "ETag": out["ETag"]})
        if self.autocommit and final: await self.commit()
        return not final
    
    async def _large_upload(self, callbacks: Optional[List[Any]] = None, **kwargs):
        """
        Handles large file uploads bc multipart upload isnt working.
        """
        bucket, key, _ = self.fs.split_path(self.path)
        _log(f"Large upload for {self}, loc={self.loc}, buffer loc={self.buffer.tell()}")
        self.buffer.seek(0)
        future = self.fs.s3tm.upload(
            self.buffer,
            bucket,
            key,
            subscribers = callbacks
        )
        res = future.result()
        _log(f"Large upload for {self} complete: {res}")
        self.buffer = io.BytesIO()

    async def commit(self):
        _log(f"Commit {self}")
        if self.tell() == 0:
            if self.buffer is not None:
                _log(f"Empty file committed {self}")
                await self._abort_mpu()
                write_result = await self.fs._touch(self.path)
        elif not self.parts:
            if self.buffer is None: raise RuntimeError
            _log(f"One-shot upload of {self}: {self.key}")
            self.buffer.seek(0)
            data = self.buffer.read()
            write_result = await self._acall_s3(
                "put_object",
                Key=self.key,
                Bucket=self.bucket,
                Body=data,
                ACL=self.acl,
                **self.kwargs,
            )
        else:
            part_info = {"Parts": self.parts}
            _log(f"Complete multi-part upload for {self}: {self.key} {part_info}")
            try:
                write_result = await self._acall_s3(
                    "complete_multipart_upload",
                    Bucket=self.bucket,
                    Key=self.key,
                    UploadId=self.mpu["UploadId"],
                    MultipartUpload=part_info,

                )
            except Exception as e:
                await self._abort_mpu()
                if 'All non-trailing' in str(e):
                    _log(f"Attempting to upload large file {self}", verbose = True)
                    try:
                        await self._large_upload()
                    except Exception as e2:
                        _log(f"Failed to upload large file {self}", verbose = True)
                        raise e2
                raise e

        if self.fs.version_aware: self.version_id = write_result.get("VersionId")
        # complex cache invalidation, since file's appearance can cause several
        # directories
        self.buffer = None
        parts = self.path.split("/")
        path = parts[0]
        for p in parts[1:]:
            if path in self.fs.dircache and not [
                True for f in self.fs.dircache[path] if f["name"] == f"{path}/{p}"
            ]: self.fs.invalidate_cache(path)
            path = f"{path}/{p}"

    
    async def write(self, data):
        """
        Write data to buffer.

        Buffer only sent on flush() or if buffer is greater than
        or equal to blocksize.

        Parameters
        ----------
        data: bytes
            Set of bytes to be written.
        """
        if self.mode not in {"wb", "ab"}: raise ValueError("File not in write mode")
        if self.closed: raise ValueError("I/O operation on closed file.")
        if self.forced: raise ValueError("This file has been force-flushed, can only close")
        out = self.buffer.write(data)
        self.loc += out
        if self.buffer.tell() >= self.blocksize: await self.flush()
        return out
    
    async def read(self, length=-1):
        if self.r is None:
            bucket, key, gen = self.fs.split_path(self.path)
            r = await self.fs._call_s3("get_object", Bucket=bucket, Key=key)
            self.size = int(r["ResponseMetadata"]["HTTPHeaders"]["content-length"])
            self.r = r["Body"]
        out = await self.r.read(length)
        self.loc += len(out)
        return out

    async def flush(self, force: bool = False):
        """
        Write buffered data to backend store.

        Writes the current buffer, if it is larger than the block-size, or if
        the file is being closed.

        Parameters
        ----------
        force: bool
            When closing, write the last block even if it is smaller than
            blocks are allowed to be. Disallows further writing to this file.
        """
        if self.closed: raise ValueError("Flush on closed file")
        if force and self.forced: raise ValueError("Force flush cannot be called more than once")
        if force: self.forced = True

        if self.mode not in {"wb", "ab"}: return
        # Defer write on small block
        if not force and self.buffer.tell() < self.blocksize: return
        if self.offset is None:
            self.offset = 0
            try: await self._initiate_upload()
            except:  # noqa: E722
                self.closed = True
                raise

        if await self._upload_chunk(final=force) is not False:
            self.offset += self.buffer.seek(0, 2)
            self.buffer = io.BytesIO()

    
    async def close(self):
        """Close file

        Finalizes writes, discards cache
        """
        if getattr(self, "_unclosable", False): return
        if self.closed: return
        if self.mode == "rb": self.cache = None
        else:
            if not self.forced: await self.flush(force=True)
            if self.fs is not None:
                self.fs.invalidate_cache(self.path)
                self.fs.invalidate_cache(self.fs._parent(self.path))

        self.closed = True

    async def discard(self):
        await self._abort_mpu()
        self.buffer = None  # file becomes unusable

    async def _abort_mpu(self):
        if self.mpu:
            await self._acall_s3(
                "abort_multipart_upload",
                Bucket=self.bucket,
                Key=self.key,
                UploadId=self.mpu["UploadId"],
            )
            self.mpu = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    