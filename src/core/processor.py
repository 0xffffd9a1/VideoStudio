import subprocess
import os
import re
from .logger import logger

def process_video(input_path: str, output_path: str,
                  start: float = None, end: float = None,
                  mode: str = 'video+audio',
                  accurate: bool = False,
                  total_duration: float = None,
                  progress_callback=None,
                  audio_filter=None):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Входной файл не найден: {input_path}")

    # Корректировка расширения
    if mode == 'audio':
        expected_ext = '.mp3'
    else:
        expected_ext = '.mp4'
    base, ext = os.path.splitext(output_path)
    if ext.lower() != expected_ext:
        logger.warning(f"Расширение '{ext}' не подходит для режима '{mode}'. "
                       f"Будет использовано '{expected_ext}'.")
        output_path = base + expected_ext

    cmd = ['ffmpeg', '-y']

    if not accurate and start is not None:
        cmd += ['-ss', str(start)]

    cmd += ['-i', input_path]

    if accurate:
        if start is not None:
            cmd += ['-ss', str(start)]
        if end is not None:
            cmd += ['-to', str(end)]
    else:
        if start is not None and end is not None:
            duration = end - start
            cmd += ['-t', str(duration)]
        elif end is not None:
            cmd += ['-to', str(end)]

    if mode == 'audio':
        cmd += ['-vn', '-c:a', 'libmp3lame']
    elif mode == 'video':
        cmd += ['-an']
        if accurate:
            cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23']
        else:
            cmd += ['-c:v', 'copy']
    elif mode == 'video+audio':
        cmd += ['-map', '0:v?', '-map', '0:a?']
        if audio_filter:
            if audio_filter == 'normalize':
                cmd += ['-af', 'loudnorm']
            elif audio_filter == 'volume_up':
                cmd += ['-af', 'volume=1.5']
            elif audio_filter == 'noise_reduce':
                cmd += ['-af', 'anlmdn']
        if accurate:
            cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k']
        else:
            cmd += ['-c', 'copy']

    cmd.append(output_path)

    logger.info(f"Выполняется: {' '.join(cmd)}")

    # Запускаем процесс с чтением stderr
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True,
                               encoding='utf-8', errors='replace')
    time_pattern = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
    # Определим общую длительность, если передана
    # для вычисления процента
    total = total_duration
    if not total:
        # Если не передана, попробуем узнать из известных start/end
        if start is not None and end is not None:
            total = end - start
        elif end is not None:
            total = end
        elif start is not None:
            total = None  # до конца, процент не определим
        else:
            total = None

    for line in process.stderr:
        if progress_callback:
            match = time_pattern.search(line)
            if match and total:
                time_str = match.group(1)
                # Преобразуем HH:MM:SS.ss в секунды
                h, m, s = time_str.split(':')
                secs = int(h)*3600 + int(m)*60 + float(s)
                if total > 0:
                    percent = min(100.0, (secs / total) * 100)
                    progress_callback(percent)

    process.wait()
    if process.returncode != 0:
        # Читаем оставшийся stderr
        err = process.stderr.read() if process.stderr else ""
        logger.error(f"Ошибка ffmpeg: {err}")
        raise subprocess.CalledProcessError(process.returncode, cmd, err)
    else:
        logger.info("Обработка успешно завершена")
        if progress_callback:
            progress_callback(100.0)