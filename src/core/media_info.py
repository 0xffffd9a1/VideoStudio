import subprocess
import json
import os
import yt_dlp
from .logger import logger

def get_local_metadata(filepath: str) -> dict:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл не найден: {filepath}")

    logger.debug(f"Извлечение метаданных локального файла: {filepath}")
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    fmt = data.get('format', {})
    duration = float(fmt.get('duration', 0))
    size_bytes = int(fmt.get('size', 0))
    title = fmt.get('tags', {}).get('title', os.path.basename(filepath))

    video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), None)
    resolution = "N/A"
    fps = "N/A"
    if video_stream:
        w = video_stream.get('width')
        h = video_stream.get('height')
        if w and h:
            resolution = f"{w}x{h}"
        fps_str = video_stream.get('r_frame_rate', '')
        if '/' in fps_str:
            num, den = fps_str.split('/')
            if float(den) != 0:
                fps = round(float(num) / float(den), 2)
        else:
            try:
                fps = round(float(fps_str), 2)
            except ValueError:
                fps = "N/A"

    metadata = {
        'title': title,
        'duration': duration,
        'resolution': resolution,
        'fps': fps,
        'size': size_bytes,
    }
    logger.info(f"Локальный файл: {metadata}")
    return metadata


def get_youtube_metadata(url: str) -> dict:
    logger.debug(f"Извлечение метаданных YouTube: {url}")
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        duration = info.get('duration', 0) or 0
        title = info.get('title', 'Unknown')
        w = info.get('width')
        h = info.get('height')
        resolution = f"{w}x{h}" if w and h else "N/A"
        fps = info.get('fps') or "N/A"
        filesize = info.get('filesize_approx') or info.get('filesize') or 0

        metadata = {
            'title': title,
            'duration': duration,
            'resolution': resolution,
            'fps': fps,
            'size': filesize,
        }
        logger.info(f"YouTube видео: {metadata}")
        return metadata