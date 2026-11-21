import subprocess
from typing import List, Optional

_CACHED_ENCODER_ARGS: Optional[List[str]] = None
_CACHED_ENCODER_NAME: Optional[str] = None


def get_h264_encoder_name() -> str:
    """
    Detect whether hardware acceleration (h264_videotoolbox) actually works in the current
    execution context (e.g. sandbox permissions, hardware capability).
    Returns 'h264_videotoolbox' if successful, otherwise 'libx264'.
    """
    global _CACHED_ENCODER_NAME
    if _CACHED_ENCODER_NAME is not None:
        return _CACHED_ENCODER_NAME
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "color=c=black:s=64x64:d=0.05", "-c:v", "h264_videotoolbox", "-f", "null", "-"
            ],
            capture_output=True, timeout=2
        )
        if r.returncode == 0:
            _CACHED_ENCODER_NAME = "h264_videotoolbox"
            return _CACHED_ENCODER_NAME
    except Exception:
        pass
    _CACHED_ENCODER_NAME = "libx264"
    return _CACHED_ENCODER_NAME


def get_h264_encoder_args() -> List[str]:
    """
    Return optimal FFmpeg encoder CLI arguments.
    For h264_videotoolbox: ['-c:v', 'h264_videotoolbox', '-q:v', '60']
    For libx264: ['-c:v', 'libx264', '-crf', '18', '-preset', 'fast']
    """
    global _CACHED_ENCODER_ARGS
    if _CACHED_ENCODER_ARGS is not None:
        return list(_CACHED_ENCODER_ARGS)
    enc = get_h264_encoder_name()
    if enc == "h264_videotoolbox":
        _CACHED_ENCODER_ARGS = ["-c:v", "h264_videotoolbox", "-q:v", "60"]
    else:
        _CACHED_ENCODER_ARGS = ["-c:v", "libx264", "-crf", "18", "-preset", "fast"]
    return list(_CACHED_ENCODER_ARGS)


def fallback_cmd_to_libx264(cmd: List[str]) -> List[str]:
    """
    Take any FFmpeg command list and replace video encoder arguments with libx264.
    """
    cmd_sw = []
    skip_next = False
    for arg in cmd:
        if skip_next:
            skip_next = False
            continue
        if arg == "-c:v":
            cmd_sw.extend(["-c:v", "libx264", "-crf", "18", "-preset", "fast"])
            skip_next = True
        elif arg in ("-q:v", "-b:v"):
            skip_next = True
        else:
            cmd_sw.append(arg)
    return cmd_sw
