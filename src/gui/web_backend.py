import sys, os, json, tempfile, threading, shutil, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import eel
from core.media_info import get_local_metadata, get_youtube_metadata
from core.downloader import download_youtube
from core.processor import process_video
from core.utils import time_to_seconds, safe_filename
from core.config import load_settings, save_settings_to_file
from core.logger import logger

settings = load_settings()
processing = False
batch_queue = []
batch_running = False
saving_in_progress = False

PRESETS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'presets.json')
try:
    with open(PRESETS_FILE, 'r') as f:
        presets = json.load(f)
except:
    presets = []

TEMP_VIDEO_DIR = os.path.join(os.path.dirname(__file__), 'web_ui', 'temp_video')
os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

# ---------- API ----------

@eel.expose
def process(data_json):
    global processing
    if processing:
        eel.addLog("⚠️ Уже выполняется обработка.")()
        return
    try:
        data = json.loads(data_json)
    except Exception as e:
        eel.addLog(f"Ошибка входных данных: {e}")()
        return
    processing = True
    eel.addLog("▶️ Начинаем обработку...")()
    thread = threading.Thread(target=_process_thread, args=(data,), daemon=True)
    thread.start()

@eel.expose
def add_to_batch(data_json):
    global batch_queue
    try:
        task = json.loads(data_json)
        batch_queue.append(task)
        eel.updateBatchList(json.dumps(batch_queue))()
        eel.addLog(f"Добавлено в очередь: {task.get('source', '')}")()
    except Exception as e:
        eel.addLog(f"Ошибка добавления в очередь: {e}")()

@eel.expose
def remove_from_batch(index):
    global batch_queue
    try:
        if 0 <= index < len(batch_queue):
            del batch_queue[index]
            eel.updateBatchList(json.dumps(batch_queue))()
            eel.addLog("Задача удалена из очереди.")()
    except Exception as e:
        eel.addLog(f"Ошибка удаления задачи: {e}")()

@eel.expose
def clear_batch():
    global batch_queue
    batch_queue = []
    eel.updateBatchList(json.dumps([]))()
    eel.addLog("Очередь очищена.")()

@eel.expose
def run_batch():
    global batch_running, processing
    if batch_running or processing:
        eel.addLog("⚠️ Пакетная обработка уже запущена.")()
        return
    if not batch_queue:
        eel.addLog("⚠️ Очередь пуста.")()
        return
    batch_running = True
    eel.addLog("▶️ Запуск пакетной обработки...")()
    thread = threading.Thread(target=_batch_thread, daemon=True)
    thread.start()

@eel.expose
def get_presets():
    return json.dumps(presets)

@eel.expose
def save_preset(name, data_json):
    global presets
    try:
        preset = {'name': name, 'settings': json.loads(data_json)}
        existing = next((p for p in presets if p['name'] == name), None)
        if existing:
            existing['settings'] = preset['settings']
        else:
            presets.append(preset)
        with open(PRESETS_FILE, 'w') as f:
            json.dump(presets, f, indent=2)
        eel.refreshPresets(json.dumps(presets))()
        eel.addLog(f"Пресет '{name}' сохранён.")()
    except Exception as e:
        eel.addLog(f"Ошибка сохранения пресета: {e}")()

@eel.expose
def delete_preset(name):
    global presets
    presets = [p for p in presets if p['name'] != name]
    with open(PRESETS_FILE, 'w') as f:
        json.dump(presets, f, indent=2)
    eel.refreshPresets(json.dumps(presets))()
    eel.addLog(f"Пресет '{name}' удалён.")()

@eel.expose
def get_video_url(source):
    if not source: return ""
    try:
        if os.path.exists(source):
            ext = os.path.splitext(source)[1]
            unique_name = str(uuid.uuid4()) + ext
            dest_path = os.path.join(TEMP_VIDEO_DIR, unique_name)
            shutil.copy2(source, dest_path)
            return f"temp_video/{unique_name}"
    except:
        return ""
    return ""

@eel.expose
def get_settings():
    return settings

@eel.expose
def save_settings(new_settings):
    global settings, saving_in_progress
    if saving_in_progress:
        return
    saving_in_progress = True
    try:
        if isinstance(new_settings, str):
            new_settings = json.loads(new_settings)

        # Проверяем, есть ли реальные изменения
        old = settings.copy()
        old.update(new_settings)
        if old == settings:
            # Ничего не изменилось — выходим без лога
            return

        settings.update(new_settings)
        save_settings_to_file(settings)
        eel.addLog("Настройки сохранены.")()
    except Exception as e:
        eel.addLog(f"Ошибка сохранения настроек: {e}")()
    finally:
        saving_in_progress = False

@eel.expose
def select_file():
    import tkinter.filedialog as fd
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    filename = fd.askopenfilename(title="Выберите видеофайл",
                                  filetypes=[("Видео", "*.mp4;*.mkv;*.webm;*.avi;*.mov"), ("Все файлы", "*.*")])
    root.destroy()
    return filename if filename else ""

@eel.expose
def select_dir():
    import tkinter.filedialog as fd
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    dirname = fd.askdirectory(title="Выберите папку для сохранения")
    root.destroy()
    return dirname if dirname else ""

# ---------- Внутренние ----------

def _process_thread(data, is_batch=False, task_index=None):
    global processing
    try:
        source = data.get('source', '').strip()
        start_str = data.get('start', '').strip()
        end_str = data.get('end', '').strip()
        mode = data.get('mode', 'video+audio')
        accurate = data.get('accurate', False)
        audio_filter = data.get('audio_filter', '')

        if not source:
            raise ValueError("Источник не указан.")
        start_sec = time_to_seconds(start_str) if start_str else None
        end_sec = time_to_seconds(end_str) if end_str else None

        prefix = f"[Задача {task_index+1}] " if is_batch else ""
        eel.addLog(prefix + "Получение информации...")()

        if source.startswith(('http://', 'https://')):
            metadata = get_youtube_metadata(source)
            eel.addLog(prefix + f"Название: {metadata['title']}")()
            eel.addLog(prefix + "Скачивание видео...")()

            def dl_progress(percent, speed_str):
                eel.setProgress(percent)()
                eel.addLog(prefix + f"Загрузка: {percent:.1f}% {speed_str}")()

            quality = settings.get("youtube_quality", "best")
            temp_dir = tempfile.gettempdir()
            local_file = download_youtube(source, temp_dir, quality=quality, progress_hook=dl_progress)
            eel.addLog(prefix + "Видео скачано.")()
            eel.setProgress(0)()
            is_temp = True
        else:
            if not os.path.exists(source):
                raise FileNotFoundError(f"Файл '{source}' не найден.")
            metadata = get_local_metadata(source)
            local_file = source
            is_temp = False

        eel.addLog(prefix + f"Длительность: {metadata['duration']:.2f} сек, {metadata['resolution']}, {metadata['fps']} fps")()

        out_dir = settings.get("output_dir") or os.getcwd()
        if not os.path.isdir(out_dir) or not os.access(out_dir, os.W_OK):
            out_dir = os.path.expanduser("~")
            eel.addLog(prefix + "⚠️ Нет доступа к папке, сохраню в домашнюю директорию.")()

        safe_title = safe_filename(metadata['title'])
        ext = '.mp3' if mode == 'audio' else '.mp4'
        output_file = os.path.normpath(os.path.join(out_dir, f"{safe_title}_processed{ext}"))

        eel.addLog(prefix + f"Обработка (режим: {mode}, точность: {accurate})...")()

        def proc_progress(percent):
            eel.setProgress(percent)()

        process_video(
            local_file, output_file,
            start_sec, end_sec, mode, accurate,
            total_duration=metadata['duration'],
            progress_callback=proc_progress,
            audio_filter=audio_filter
        )
        eel.addLog(prefix + f"✅ Готово: {output_file}")()

        if is_temp:
            try: os.remove(local_file)
            except: pass

    except Exception as e:
        logger.exception("Ошибка обработки")
        eel.addLog(prefix + f"❌ Ошибка: {e}")()
    finally:
        processing = False
        eel.setProgress(0)()

def _batch_thread():
    global batch_running, processing
    for i, task in enumerate(batch_queue):
        processing = True
        _process_thread(task, is_batch=True, task_index=i)
        processing = False
    batch_running = False
    eel.addLog("✅ Пакетная обработка завершена.")()

def expose_functions():
    pass