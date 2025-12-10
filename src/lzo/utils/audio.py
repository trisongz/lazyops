from __future__ import annotations

"""
Audio Utilities
"""

import io
import os
import re
import json
import base64
import shutil
import asyncio
import subprocess
import pathlib
import tempfile
import functools
import typing as t
from lzl import load
from lzl.logging import logger
from dataclasses import dataclass

if t.TYPE_CHECKING:
    import pydub
    from lzl.io import File
else:
    pydub = load.lazy_load("pydub")


tempdir = pathlib.Path(tempfile.gettempdir())

@functools.lru_cache(maxsize=1)
def _has_ffmpeg() -> bool:
    """
    Check if ffmpeg is available in the system.
    """
    return shutil.which("ffmpeg") is not None

def ensure_ffmpeg():
    """
    Ensure that ffmpeg is available in the system. Raise an error if not.
    """
    if not _has_ffmpeg():
        raise EnvironmentError("ffmpeg is not available in the system. Please install ffmpeg to use audio utilities.")


def _parse_sample_rate(sr: t.Union[int, str]) -> int:
    """
    Helper to handle inputs like '16000', '16k', '16khz'.
    """
    if isinstance(sr, int):
        return sr
    
    clean = str(sr).lower().strip()
    if "k" in clean:
        # Extract numbers, multiply by 1000
        nums = re.findall(r"[\d\.]+", clean)
        if nums:
            return int(float(nums[0]) * 1000)
    
    # Fallback: try direct conversion
    return int(re.sub(r"[^\d]", "", clean))


@dataclass
class AudioMetadata:
    format: str
    duration: float
    channels: int
    sample_rate: int
    bit_rate: int
    codec: str

def get_audio_metadata(
    file_path: 'File'
) -> AudioMetadata:
    """
    Uses ffprobe to inspect the file without decoding it.
    Crucial for 'Router Logic' to decide how to process the file.
    """
    ensure_ffmpeg()
    from lzl.io import File
    file_path = File(file_path)
    if not file_path.is_local_obj_:
        file_path = file_path.localize(cleanup_on_exit=True)

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path.as_posix(),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"Could not probe file: {file_path}")
        
    data = json.loads(result.stdout)
    
    # Extract audio stream (usually the first one)
    audio_stream = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not audio_stream:
        raise ValueError("No audio stream found.")

    return AudioMetadata(
        format=data["format"]["format_name"],
        duration=float(data["format"].get("duration", 0)),
        channels=int(audio_stream.get("channels", 1)),
        sample_rate=int(audio_stream.get("sample_rate", 0)),
        bit_rate=int(data["format"].get("bit_rate", 0)),
        codec=audio_stream.get("codec_name", "unknown")
    )


async def aget_audio_metadata(
    file_path: 'File'
) -> AudioMetadata:
    """
    Uses ffprobe to inspect the file without decoding it.
    Crucial for 'Router Logic' to decide how to process the file.
    """
    ensure_ffmpeg()
    from lzl.io import File
    file_path = File(file_path)
    if not file_path.is_local_obj_:
        file_path = await file_path.alocalize(cleanup_on_exit=True)

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path.as_posix(),
    ]
    result = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await result.communicate()

    if result.returncode != 0:
        raise ValueError(f"Could not probe file: {file_path}: {stderr.decode()}")
    
    data = json.loads(stdout.decode())
    # Extract audio stream (usually the first one)
    audio_stream = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not audio_stream:
        raise ValueError("No audio stream found.")

    return AudioMetadata(
        format=data["format"]["format_name"],
        duration=float(data["format"].get("duration", 0)),
        channels=int(audio_stream.get("channels", 1)),
        sample_rate=int(audio_stream.get("sample_rate", 0)),
        bit_rate=int(data["format"].get("bit_rate", 0)),
        codec=audio_stream.get("codec_name", "unknown")
    )


def normalize_audio_file(
    file: 'File', 
    target: t.Literal['wav', 'mp3'] = 'wav', 
    channels: t.Optional[int] = 1, 
    sr: t.Union[int, str] = 16000, 
    output_path: t.Optional['File'] = None, 
    temp: t.Optional[bool] = False,
    save_remote: t.Optional[bool] = False,
    overwrite: t.Optional[bool] = False,
    **kwargs
) -> 'File':
    """
    Robustly normalizes audio to a standard format for ML training.
    It should always return a localized file path.
    
    Args:
        file: Input file path.
        target: 'wav' (uncompressed) or 'mp3'. 
                Use 'wav' for training (Whisper prefers uncompressed).
        channels: 1 for Mono, 2 for Stereo. 
                  If None, preserves the original channel count.
        sr: Sample rate (e.g., 16000 or '16khz').
        output_path: Destination. If None, appends '_normalized' to filename.
        temp: If True, treat output as temporary file (cleanup later).
        save_remote: If True and output_path is remote, upload after processing.
        overwrite: If True, overwrite existing files.
        **kwargs: 
            - 'acodec': Override codec (e.g., 'pcm_f32le'). Default is 'pcm_s16le'.
    """
    ensure_ffmpeg()
    from lzl.io import File
    file = File(file)
    if not file.exists():
        raise FileNotFoundError(f"Input file not found: {file}")

    # 1. Standardize Inputs
    target_sr = _parse_sample_rate(sr)
    
    # 2. Determine Output Path
    target_output_path: t.Optional[File] = None
    
    # output_path will always be the local, whereas
    # target_output_path may be remote if save_remote is True
    if output_path is None or output_path.is_dir():
        name_stem = file.stem
        # add <sr>khz to filename
        name_stem += f"_{target_sr//1000}khz"
        if channels is not None:
            ch = "mono" if channels == 1 else "stereo"
            name_stem += f"_{ch}"    
        if output_path and output_path.is_dir():
            output_path = output_path.joinpath(f"{name_stem}.{target}")
        else:
            output_path = file.parent.joinpath(f"{name_stem}.{target}")

    else:
        output_path = File(output_path)

    # Ensure output directory exists 
    if output_path.is_local_obj_:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_output_path = output_path
    else:
        # Local temp path for processing
        target_output_path = tempdir.joinpath(output_path.name)
        target_output_path = File(target_output_path)

    # Check if output_path is remote and we need to save remotely
    if not overwrite and output_path.exists():
        if not output_path.is_local_obj_:
            output_path = output_path.localize(cleanup_on_exit=bool(temp))
        return output_path
    
    if not file.is_local_obj_:
        file = file.localize(cleanup_on_exit=True)
    
    # 3. Construct FFmpeg Command
    # Start with input
    cmd = ["ffmpeg", "-i", str(file)]
    
    # Verbosity (hide banner info)
    cmd += ["-hide_banner", "-loglevel", "error"]
    
    # Sample Rate
    cmd += ["-ar", str(target_sr)]
    
    # Channels
    if channels is not None: cmd += ["-ac", str(channels)]

    # If channels is None, ffmpeg defaults to "same as input"
    # Codec & Format Logic
    if target == 'wav':
        # CRITICAL for Whisper: 
        # Default to PCM 16-bit Little Endian. 
        # Many ML loaders fail on 32-bit float WAVs or weird headers.
        codec = kwargs.get('acodec', 'pcm_s16le') 
        cmd += ["-c:a", codec]
        cmd += ["-f", "wav"]
    elif target == 'mp3':
        cmd += ["-c:a", "libmp3lame"]
        cmd += ["-q:a", "2"] # High quality VBR
        cmd += ["-f", "mp3"]
        
    # Overwrite logic
    if overwrite:
        cmd.append("-y")
    else:
        cmd.append("-n")

    # Output
    cmd.append(target_output_path.as_posix())

    # 4. Execute
    try:
        # We run this synchronously. For massive batches, use multiprocessing.Pool 
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        # Decode error for debugging
        err_msg = e.stderr.decode().strip()
        raise RuntimeError(f"FFmpeg failed on {file.name}: {err_msg}") from e

    # 5. Handle Remote Saving
    if save_remote and output_path.is_cloud_obj_:
        target_output_path.copy_to(output_path, overwrite=overwrite)

    return target_output_path


async def anormalize_audio_file(
    file: 'File', 
    target: t.Literal['wav', 'mp3'] = 'wav', 
    channels: t.Optional[int] = 1, 
    sr: t.Union[int, str] = 16000, 
    output_path: t.Optional['File'] = None, 
    temp: t.Optional[bool] = False,
    save_remote: t.Optional[bool] = False,
    overwrite: t.Optional[bool] = False,
    **kwargs
) -> 'File':
    """
    Robustly normalizes audio to a standard format for ML training.
    It should always return a localized file path.
    
    Args:
        file: Input file path.
        target: 'wav' (uncompressed) or 'mp3'. 
                Use 'wav' for training (Whisper prefers uncompressed).
        channels: 1 for Mono, 2 for Stereo. 
                  If None, preserves the original channel count.
        sr: Sample rate (e.g., 16000 or '16khz').
        output_path: Destination. If None, appends '_normalized' to filename.
        temp: If True, treat output as temporary file (cleanup later).
        save_remote: If True and output_path is remote, upload after processing.
        overwrite: If True, overwrite existing files.
        **kwargs: 
            - 'acodec': Override codec (e.g., 'pcm_f32le'). Default is 'pcm_s16le'.
    """
    ensure_ffmpeg()
    from lzl.io import File
    file = File(file)
    if not file.exists():
        raise FileNotFoundError(f"Input file not found: {file}")

    # 1. Standardize Inputs
    target_sr = _parse_sample_rate(sr)
    
    # 2. Determine Output Path
    target_output_path: t.Optional[File] = None
    
    # output_path will always be the local, whereas
    # target_output_path may be remote if save_remote is True
    if output_path is None or output_path.is_dir():
        name_stem = file.stem
        # add <sr>khz to filename
        name_stem += f"_{target_sr//1000}khz"
        if channels is not None:
            ch = "mono" if channels == 1 else "stereo"
            name_stem += f"_{ch}"    
        if output_path and output_path.is_dir():
            output_path = output_path.joinpath(f"{name_stem}.{target}")
        else:
            output_path = file.parent.joinpath(f"{name_stem}.{target}")

    else:
        output_path = File(output_path)

    # Ensure output directory exists 
    if output_path.is_local_obj_:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        target_output_path = output_path
    else:
        # Local temp path for processing
        target_output_path = tempdir.joinpath(output_path.name)
        target_output_path = File(target_output_path)

    # Check if output_path is remote and we need to save remotely
    if not overwrite and await output_path.aexists():
        if not output_path.is_local_obj_:
            output_path = await output_path.alocalize(cleanup_on_exit=bool(temp))
        return output_path
    
    if not file.is_local_obj_:
        file = await file.alocalize(cleanup_on_exit=True)
    
    # 3. Construct FFmpeg Command
    # Start with input
    cmd = ["ffmpeg", "-i", str(file)]
    
    # Verbosity (hide banner info)
    cmd += ["-hide_banner", "-loglevel", "error"]
    
    # Sample Rate
    cmd += ["-ar", str(target_sr)]
    
    # Channels
    if channels is not None: cmd += ["-ac", str(channels)]

    # If channels is None, ffmpeg defaults to "same as input"
    # Codec & Format Logic
    if target == 'wav':
        # CRITICAL for Whisper: 
        # Default to PCM 16-bit Little Endian. 
        # Many ML loaders fail on 32-bit float WAVs or weird headers.
        codec = kwargs.get('acodec', 'pcm_s16le') 
        cmd += ["-c:a", codec]
        cmd += ["-f", "wav"]
    elif target == 'mp3':
        cmd += ["-c:a", "libmp3lame"]
        cmd += ["-q:a", "2"] # High quality VBR
        cmd += ["-f", "mp3"]
        
    # Overwrite logic
    if overwrite:
        cmd.append("-y")
    else:
        cmd.append("-n")

    # Output
    cmd.append(target_output_path.as_posix())

    # 4. Execute

    # We run this asynchronously. For massive batches, use multiprocessing.Pool
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg failed on {file.name}: {stderr.decode().strip()}")
        
    # 5. Handle Remote Saving
    if save_remote and output_path.is_cloud_obj_:
        await target_output_path.acopy_to(output_path, overwrite=overwrite)
    return target_output_path




ExtensionMapping: t.Dict[str, str] = {
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.flac': 'audio/flac',
}

def prepare_audio_file_encoded(
    file_path: 'File',
    content_type: t.Optional[str] = None,
) -> str:
    """
    Prepare the audio file for processing by encoding it to a base64.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")
    audio_bytes = file_path.read_bytes()
    media_type = ExtensionMapping.get(file_path.suffix, content_type or 'unknown')
    if media_type == 'unknown':
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    encoded = base64.b64encode(audio_bytes).decode('utf-8')
    return f"data:{media_type};base64,{encoded}"

async def aprepare_audio_file_encoded(
    file_path: 'File',
    content_type: t.Optional[str] = None,
) -> str:
    """
    Prepare the audio file for processing by encoding it to a base64.
    """
    if not await file_path.aexists():
        raise FileNotFoundError(f"File {file_path} does not exist.")

    audio_bytes = await file_path.aread_bytes()
    media_type = ExtensionMapping.get(file_path.suffix, content_type or 'unknown')
    if media_type == 'unknown':
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
    encoded = base64.b64encode(audio_bytes).decode('utf-8')
    return f"data:{media_type};base64,{encoded}"


def prepare_wav_file(fp: 'File') -> 'File':
    """
    Prepares and ensures that the file is a valid local WAV file.
    """
    if fp.is_cloud_obj_:
        if fp.content_type_ in {'audio/wav', 'audio/x-wav'}:
            return fp.localize(cleanup_on_exit=True)
        else:
            fp = fp.localize(filename=fp.with_suffix('.wav').name, cleanup_on_exit=True)
    
    elif fp.suffix == '.wav': return fp
    
    import io
    # Convert mp3 to wav
    sound: 'pydub.AudioSegment' = pydub.AudioSegment.from_mp3(fp.as_posix())
    sound = sound.set_frame_rate(16000)
    sound = sound.set_channels(1)
    buffer = io.BytesIO()
    sound.export(buffer, format='wav')
    buffer.seek(0)
    fp.write_bytes(buffer.read())
    return fp

def create_wav_file(fp: 'File', output: t.Optional['File'] = None, truncate: t.Optional[float] = None, overwrite: t.Optional[bool] = None) -> 'File':
    """
    Creates a WAV file from the given audio file, optionally truncating it to a specified duration.

    Args:
        fp: Input audio file (can be local or cloud)
        output: Optional output file path
        truncate: Optional duration in seconds to truncate the audio
        overwrite: Optional flag to overwrite the output file if it exists
    Returns:
        A local WAV file
    """
    import io
    from lzl.io import File
    fp = File(fp)

    if fp.is_cloud_obj_:
        fp = fp.localize(cleanup_on_exit=True)
    
    if not output:
        if truncate: output = fp.with_suffix(f'_truncated{truncate:.0f}s.wav')
        else: output = fp.with_suffix('.wav')
    else: output = File(output)

    if output.exists() and not overwrite:
        logger.info(f"WAV file {output} already exists, skipping creation")
        return output

    # Convert mp3 to wav
    sound: 'pydub.AudioSegment' = pydub.AudioSegment.from_file(fp.as_posix())
    sound = sound.set_frame_rate(16000)
    sound = sound.set_channels(1)
    if truncate: sound = sound[:int(truncate * 1000)]
    buffer = io.BytesIO()
    sound.export(buffer, format='wav')
    buffer.seek(0)
    output.write_bytes(buffer.read())
    return output


async def aprepare_wav_file(fp: 'File') -> 'File':
    """
    Prepares and ensures that the file is a valid local WAV file.
    """
    if fp.is_cloud_obj_:
        if fp.content_type_ in {'audio/wav', 'audio/x-wav'}:
            return await fp.alocalize(cleanup_on_exit=True)
        else:
            fp = await fp.alocalize(filename=fp.with_suffix('.wav').name, cleanup_on_exit=True)
    elif fp.suffix == '.wav': return fp
    import io

    # Convert mp3 to wav
    sound: 'pydub.AudioSegment' = pydub.AudioSegment.from_mp3(fp.as_posix())
    sound = sound.set_frame_rate(16000)
    sound = sound.set_channels(1)
    buffer = io.BytesIO()
    sound.export(buffer, format='wav')
    buffer.seek(0)
    await fp.awrite_bytes(buffer.read())
    return fp


async def acreate_wav_file(
    fp: 'File', 
    output: t.Optional['File'] = None, 
    truncate: t.Optional[float] = None, 
    overwrite: t.Optional[bool] = None
) -> 'File':
    """
    Creates a WAV file from the given audio file, optionally truncating it to a specified duration.

    Args:
        fp: Input audio file (can be local or cloud)
        output: Optional output file path
        truncate: Optional duration in seconds to truncate the audio
        overwrite: Optional flag to overwrite the output file if it exists

    Returns:
        A local WAV file
    """
    import io
    from lzl.io import File
    fp = File(fp)

    if fp.is_cloud_obj_:
        fp = await fp.alocalize(cleanup_on_exit=True)
    
    if not output:
        if truncate: 
            output = fp.with_name(f'{fp.stem}_truncated{truncate:.0f}s.wav')
            # output = fp.with_suffix(f'_truncated{truncate:.0f}s.wav')
        else: output = fp.with_suffix('.wav')
    else: output = File(output)

    if await output.aexists() and not overwrite:
        logger.info(f"WAV file {output} already exists, skipping creation")
        return output

    # Convert mp3 to wav
    sound: 'pydub.AudioSegment' = pydub.AudioSegment.from_file(fp.as_posix())
    sound = sound.set_frame_rate(16000)
    sound = sound.set_channels(1)
    if truncate: sound = sound[:int(truncate * 1000)]
    buffer = io.BytesIO()
    sound.export(buffer, format='wav')
    buffer.seek(0)
    await output.awrite_bytes(buffer.read())
    return output
