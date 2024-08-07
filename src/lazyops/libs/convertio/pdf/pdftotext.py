from __future__ import annotations

"""
A File Conversion based on PDFtoText

- Requires pdftotext to be installed
"""
import os
import asyncio
import subprocess
from pathlib import Path
from ..base import (
    BaseConverter, 
    OutputType, 
    InputContentType, 
    InputPathType, 
    InputSourceType, 
    InvalidSourceError, 
    InvalidTargetError
)

from typing import Any, Union, Optional, Type, Iterable, Callable, Dict, List, Tuple, TypeVar


class PDFtoTextConverter(BaseConverter):

    name: str = 'pdftotext'
    source: str = 'pdf'
    targets: List[str] = ['txt', 'text']
    async_enabled: bool = True


    def validate_enabled(self, **kwargs) -> bool:
        """
        Validate whether the converter is enabled
        """
        from shutil import which

        return which('pdftotext') is not None

    
    def _convert_source_to_target(
        self,
        source: InputSourceType,
        target: Optional[str] = '.txt', 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        raise_errors: Optional[bool] = False,
        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.txt'
        """
        if not self.is_valid_target_content_type(target):
            raise InvalidTargetError(self, target)

        target_output_path = Path(target_output) if target_output else None
        if target_output_path and target_output_path.is_dir():
            if not source_filename and isinstance(source, str):
                target_filename = Path(source).with_suffix(target).name
            else:
                target_filename = f'output{target}'
            target_output_path = target_output_path.joinpath(target_filename)
        
        source_file = self.convert_file_input_to_file(source, source_filename, make_temp = True)
        cmd = f'cat "{source_file.as_posix()}" | pdftotext -layout -nopgbrk -eol unix -colspacing 0.7 -y 58 -x 0 -H 741 -W 596 - -'
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate()
            stdout = stdout.decode('utf-8')
            os.unlink(source_file.as_posix())
            if target_output_path:
                target_output_path.parent.mkdir(parents=True, exist_ok=True)
                target_output_path.write_text(stdout)
                return target_output_path
            return stdout
        except Exception as e:
            stderr = stderr.decode('utf-8')
            self.logger.error(f'Error in pdftotext: {stderr}: {e}')
            os.unlink(source_file.as_posix())
            if raise_errors: raise e
            return None


    async def _aconvert_source_to_target(
        self,
        source: InputSourceType,
        target: Optional[str] = '.txt', 

        source_filename: Optional[str] = None,
        target_output: Optional[Any] = None,

        raise_errors: Optional[bool] = False,
        **kwargs,
    ) -> OutputType:
        """
        Convert the source to the target

        source: /path/to/file.pdf
        target: '.txt'
        """
        if not self.is_valid_target_content_type(target):
            raise InvalidTargetError(self, target)

        target_output_path = Path(target_output) if target_output else None
        if target_output_path and target_output_path.is_dir():
            if not source_filename and isinstance(source, str):
                target_filename = Path(source).with_suffix(target).name
            else:
                target_filename = f'output{target}'
            target_output_path = target_output_path.joinpath(target_filename)
        
        source_file = self.convert_file_input_to_file(source, source_filename, make_temp = True)
        cmd = f'cat "{source_file.as_posix()}" | pdftotext -layout -nopgbrk -eol unix -colspacing 0.7 -y 58 -x 0 -H 741 -W 596 - -'
        process = await asyncio.subprocess.create_subprocess_shell(cmd, shell=True, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await process.communicate()
            stdout = stdout.decode('utf-8')
            os.unlink(source_file.as_posix())
            if target_output_path:
                target_output_path.parent.mkdir(parents=True, exist_ok=True)
                target_output_path.write_text(stdout)
                return target_output_path
            return stdout
        except Exception as e:
            stderr = stderr.decode('utf-8')
            self.logger.error(f'Error in pdftotext: {stderr}: {e}')
            os.unlink(source_file.as_posix())
            if raise_errors: raise e
            return None
            
