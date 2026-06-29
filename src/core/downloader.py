import yt_dlp
import os
from .logger import logger

QUALITY_FORMATS = {
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "audio_only": "bestaudio[ext=m4a]/bestaudio/best"
}

def download_youtube(url: str, output_dir: str, quality="best", progress_hook=None) -> str:
    out_template = os.path.join(output_dir, 'video.%(ext)s')
    format_str = QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])

    def hook(d):
        if progress_hook:
            if d['status'] == 'downloading':
                # Вычисляем процент
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0)
                if total:
                    percent = downloaded / total * 100
                else:
                    percent = 0
                progress_hook(percent, d.get('_speed_str', ''))
            elif d['status'] == 'finished':
                progress_hook(100.0, '')

    ydl_opts = {
        'format': format_str,
        'merge_output_format': 'mp4' if 'audio' not in quality else 'm4a',
        'outtmpl': out_template,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'socket_timeout': 30,
        'retries': 3,
        'ignoreerrors': False,
        'overwrites': True,
        'progress_hooks': [hook],
    }

    logger.debug(f"Скачивание: {url}, качество={quality}")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        logger.error(f"Ошибка скачивания: {e}")
        raise RuntimeError(f"Не удалось скачать видео: {e}")

    ext = 'mp4' if 'audio' not in quality else 'm4a'
    downloaded_file = os.path.join(output_dir, f'video.{ext}')
    if not os.path.exists(downloaded_file):
        candidates = [f for f in os.listdir(output_dir) if f.startswith('video.')]
        if candidates:
            downloaded_file = os.path.join(output_dir, candidates[0])
        else:
            raise FileNotFoundError("Скачанный файл не найден.")
    logger.info(f"Видео сохранено: {downloaded_file}")
    return downloaded_file