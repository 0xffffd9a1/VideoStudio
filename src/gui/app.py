import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sv_ttk
import os
import sys
import tempfile
import threading
import queue

# Настройка импорта ядра
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.media_info import get_local_metadata, get_youtube_metadata
from core.downloader import download_youtube
from core.processor import process_video
from core.utils import time_to_seconds, safe_filename
from core.config import load_settings, save_settings
from core.logger import logger


class VideoStudioApp:
    def __init__(self, master):
        self.master = master
        master.title("VideoStudio")
        master.geometry("700x580")
        master.resizable(True, True)
        master.minsize(600, 480)

        # Настройки
        self.settings = load_settings()
        # Применяем тему (светлая/тёмная) через sv_ttk
        self._apply_theme()

        # Очередь сообщений и состояние обработки
        self.msg_queue = queue.Queue()
        self.processing = False

        # ---------- Переменные интерфейса ----------
        self.source_var = tk.StringVar()
        self.start_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="video+audio")
        self.accurate_var = tk.BooleanVar(value=False)

        # ---------- Drag‑and‑Drop ----------
        master.drop_target_register('*')
        master.dnd_bind('<<Drop>>', self._on_drop)

        # ---------- Стили ----------
        self._setup_styles()

        # ---------- Сборка интерфейса ----------
        self._create_widgets()
        self._create_menu()

        # Периодическая проверка очереди сообщений
        self.master.after(100, self._check_queue)

    def _apply_theme(self):
        theme = self.settings.get("appearance_mode", "Dark")
        if theme.lower() == "light":
            sv_ttk.set_theme("light")
        else:
            sv_ttk.set_theme("dark")

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 11))
        style.configure("Card.TFrame", relief="flat", borderwidth=0)
        style.configure("Process.TButton", font=("Segoe UI", 12, "bold"))

    # ------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------
    def _create_widgets(self):
        # Заголовок
        ttk.Label(self.master, text="VideoStudio", style="Title.TLabel").pack(pady=(15, 5))
        ttk.Label(self.master, text="Извлечение аудио и видео · YouTube и локальные файлы",
                  style="Subtitle.TLabel").pack(pady=(0, 15))

        # Карточка источника
        source_frame = ttk.Frame(self.master, style="Card.TFrame", padding=10)
        source_frame.pack(fill="x", padx=15, pady=5)
        ttk.Label(source_frame, text="Источник", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        entry_frame = ttk.Frame(source_frame)
        entry_frame.pack(fill="x")
        self.entry_source = ttk.Entry(entry_frame, textvariable=self.source_var)
        self.entry_source.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_source.bind("<Button-3>", lambda e: self._popup_entry_menu(e, self.entry_source))
        ttk.Button(entry_frame, text="Обзор", command=self._browse_file).pack(side="right")

        # Карточка времени
        time_frame = ttk.Frame(self.master, style="Card.TFrame", padding=10)
        time_frame.pack(fill="x", padx=15, pady=5)
        ttk.Label(time_frame, text="Время", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(time_frame, text="Начало (ММ:СС)").grid(row=1, column=0, padx=(0, 5), sticky="w")
        ttk.Entry(time_frame, textvariable=self.start_var, width=15).grid(row=2, column=0, padx=(0, 5), sticky="ew")
        ttk.Label(time_frame, text="Конец (ММ:СС)").grid(row=1, column=1, padx=(5, 0), sticky="w")
        ttk.Entry(time_frame, textvariable=self.end_var, width=15).grid(row=2, column=1, padx=(5, 0), sticky="ew")
        time_frame.grid_columnconfigure((0, 1), weight=1)

        # Карточка режима
        mode_frame = ttk.Frame(self.master, style="Card.TFrame", padding=10)
        mode_frame.pack(fill="x", padx=15, pady=5)
        ttk.Label(mode_frame, text="Режим", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        mode_menu = ttk.Combobox(mode_frame, textvariable=self.mode_var,
                                 values=["video+audio", "audio", "video"], state="readonly")
        mode_menu.pack(fill="x")

        # Точная обрезка
        self.accurate_check = ttk.Checkbutton(self.master,
            text="Точная обрезка (перекодирование, медленно, нагрузка на процессор)",
            variable=self.accurate_var)
        self.accurate_check.pack(padx=15, pady=10, anchor="w")

        # Прогресс‑бар
        self.progress = ttk.Progressbar(self.master, mode="determinate", length=400)
        self.progress.pack(fill="x", padx=15, pady=5)
        self.progress["value"] = 0

        # Кнопка обработки
        self.btn_process = ttk.Button(self.master, text="Обработать",
                                      command=self._start_processing, style="Process.TButton")
        self.btn_process.pack(pady=10)

        # Лог (Text с полосой прокрутки)
        log_frame = ttk.Frame(self.master)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled",
                                font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _create_menu(self):
        # Кнопка настроек (в правом верхнем углу)
        self.btn_settings = ttk.Button(self.master, text="⚙️", width=3, command=self._open_settings)
        self.btn_settings.place(relx=0.95, rely=0.02, anchor="ne")

    # ------------------------------------------------------------
    #  Drag‑and‑Drop, контекстное меню, выбор файла
    # ------------------------------------------------------------
    def _on_drop(self, event):
        files = self.master.tk.splitlist(event.data)
        if files:
            path = files[0]
            if path.lower().endswith(('.mp4', '.mkv', '.webm', '.avi', '.mov')):
                self.source_var.set(path)
                logger.info(f"Файл перетащен: {path}")
            elif path.startswith(('http://', 'https://')):
                self.source_var.set(path)
                logger.info(f"Ссылка перетащена: {path}")
            else:
                messagebox.showwarning("Неверный формат", "Перетащите видеофайл или ссылку YouTube.")

    def _popup_entry_menu(self, event, entry):
        menu = tk.Menu(self.master, tearoff=0)
        menu.add_command(label="Вставить", command=lambda: entry.insert("insert", self.master.clipboard_get()))
        menu.add_command(label="Копировать", command=lambda: self.master.clipboard_append(entry.get()))
        menu.add_command(label="Вырезать", command=lambda: self.master.clipboard_append(entry.get()) or entry.delete(0, "end"))
        menu.tk_popup(event.x_root, event.y_root)

    def _browse_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите видеофайл",
            filetypes=[("Видео файлы", "*.mp4 *.mkv *.webm *.avi *.mov"), ("Все файлы", "*.*")]
        )
        if filename:
            self.source_var.set(filename)

    # ------------------------------------------------------------
    #  Обработка
    # ------------------------------------------------------------
    def _start_processing(self):
        if self.processing:
            messagebox.showwarning("Подождите", "Обработка уже выполняется.")
            return

        source = self.source_var.get().strip()
        if not source:
            messagebox.showerror("Ошибка", "Введите источник.")
            return

        start_str = self.start_var.get().strip()
        end_str = self.end_var.get().strip()
        mode = self.mode_var.get()
        accurate = self.accurate_var.get()

        if accurate:
            try:
                if source.startswith(('http://', 'https://')):
                    meta = get_youtube_metadata(source)
                else:
                    meta = get_local_metadata(source)
                res = meta.get('resolution', '')
                if 'x' in res:
                    w_str, h_str = res.split('x')
                    w, h = int(w_str), int(h_str)
                    if w * h > 1920 * 1080:
                        ok = messagebox.askokcancel(
                            "Высокая нагрузка",
                            f"Включён точный режим с перекодированием. Видео имеет разрешение {w}x{h}. "
                            "Это может сильно нагрузить процессор и занять много времени.\n\n"
                            "Рекомендуется отключить точный режим, если не нужна покадровая точность.\n\n"
                            "Продолжить?"
                        )
                        if not ok:
                            return
            except Exception:
                pass

        start_sec = None
        end_sec = None
        try:
            if start_str:
                start_sec = time_to_seconds(start_str)
            if end_str:
                end_sec = time_to_seconds(end_str)
        except ValueError as e:
            messagebox.showerror("Ошибка", f"Неверный формат времени: {e}")
            return

        self._set_processing(True)
        thread = threading.Thread(
            target=self._process_thread,
            args=(source, start_sec, end_sec, mode, accurate),
            daemon=True
        )
        thread.start()

    def _process_thread(self, source, start_sec, end_sec, mode, accurate):
        try:
            self.msg_queue.put("Получение информации об источнике...")
            if source.startswith(('http://', 'https://')):
                metadata = get_youtube_metadata(source)
                self.msg_queue.put(f"Название: {metadata['title']}")
                self.msg_queue.put("Скачивание видео...")
                temp_dir = tempfile.gettempdir()

                def dl_progress(percent, speed_str):
                    self.msg_queue.put(f"Загрузка: {percent:.1f}% {speed_str}")
                    self._update_progress(percent)

                quality = self.settings.get("youtube_quality", "best")
                local_file = download_youtube(source, temp_dir, quality=quality, progress_hook=dl_progress)
                self.msg_queue.put("Видео скачано.")
                self._update_progress(0)
                is_temp = True
            else:
                if not os.path.exists(source):
                    raise FileNotFoundError(f"Файл '{source}' не найден.")
                metadata = get_local_metadata(source)
                local_file = source
                is_temp = False

            self.msg_queue.put(f"Длительность: {metadata['duration']:.2f} сек, "
                               f"Разрешение: {metadata['resolution']}, FPS: {metadata['fps']}")

            # Определяем папку сохранения
            out_dir = self.settings.get("output_dir") or os.getcwd()
            if not os.path.isdir(out_dir) or not os.access(out_dir, os.W_OK):
                out_dir = os.path.expanduser("~")  # домашняя папка пользователя
                self.msg_queue.put("Внимание: нет доступа к целевой папке, сохраняю в домашнюю директорию.")

            safe_title = safe_filename(metadata['title'])
            ext = '.mp3' if mode == 'audio' else '.mp4'
            output_file = os.path.normpath(os.path.join(out_dir, f"{safe_title}_processed{ext}"))
            safe_title = safe_filename(metadata['title'])
            ext = '.mp3' if mode == 'audio' else '.mp4'
            output_file = os.path.join(out_dir, f"{safe_title}_processed{ext}")

            self.msg_queue.put(f"Обработка (режим: {mode}, точность: {accurate})...")
            if accurate:
                self.msg_queue.put("ВНИМАНИЕ: точный режим, ожидайте.")

            def proc_progress(percent):
                self._update_progress(percent)

            process_video(local_file, output_file, start_sec, end_sec, mode, accurate,
                          total_duration=metadata['duration'], progress_callback=proc_progress)
            self.msg_queue.put(f"Готово! Результат: {os.path.abspath(output_file)}")

            if is_temp:
                try:
                    os.remove(local_file)
                except Exception:
                    pass

            self.master.after(0, lambda: messagebox.showinfo("Успех",
                                                             f"Обработка завершена.\nФайл: {output_file}"))

        except Exception as e:
            logger.exception("Ошибка обработки")
            self.msg_queue.put(f"ОШИБКА: {e}")
            self.master.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
        finally:
            self.master.after(0, lambda: self._set_processing(False))

    def _update_progress(self, value):
        self.master.after(0, lambda: self.progress.configure(value=value))

    def _set_processing(self, value):
        self.processing = value
        if value:
            self.btn_process.configure(state="disabled")
        else:
            self.btn_process.configure(state="normal")
            self.progress.configure(value=0)

    # ------------------------------------------------------------
    #  Лог и очередь сообщений
    # ------------------------------------------------------------
    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _check_queue(self):
        while not self.msg_queue.empty():
            msg = self.msg_queue.get_nowait()
            self._log(msg)
        self.master.after(100, self._check_queue)

    # ------------------------------------------------------------
    #  Настройки
    # ------------------------------------------------------------
    def _open_settings(self):
        dialog = tk.Toplevel(self.master)
        dialog.title("Настройки")
        dialog.geometry("400x350")
        dialog.resizable(False, False)
        dialog.transient(self.master)
        dialog.grab_set()

        notebook = ttk.Notebook(dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab1 = ttk.Frame(notebook)
        tab2 = ttk.Frame(notebook)
        notebook.add(tab1, text="Основные")
        notebook.add(tab2, text="YouTube")

        # Папка сохранения
        ttk.Label(tab1, text="Папка сохранения:").pack(anchor="w", pady=5)
        dir_frame = ttk.Frame(tab1)
        dir_frame.pack(fill="x")
        self.output_dir_var = tk.StringVar(value=self.settings.get("output_dir", ""))
        ttk.Entry(dir_frame, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(dir_frame, text="Обзор", command=lambda: self._browse_output_dir(self.output_dir_var)).pack(side="right")

        # Тема
        ttk.Label(tab1, text="Тема оформления:").pack(anchor="w", pady=5)
        self.theme_var = tk.StringVar(value=self.settings["appearance_mode"])
        ttk.OptionMenu(tab1, self.theme_var, self.settings["appearance_mode"], "Dark", "Light", command=self._change_theme).pack(fill="x")

        # Качество YouTube
        ttk.Label(tab2, text="Качество загрузки:").pack(anchor="w", pady=5)
        self.quality_var = tk.StringVar(value=self.settings.get("youtube_quality", "best"))
        quality_menu = ttk.OptionMenu(tab2, self.quality_var, self.settings.get("youtube_quality", "best"),
                                       "best", "1080p", "720p", "audio_only")
        quality_menu.pack(fill="x")

        # Кнопки
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text="Сохранить", command=lambda: self._save_settings(dialog)).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Отмена", command=dialog.destroy).pack(side="right")

    def _browse_output_dir(self, var):
        dirname = filedialog.askdirectory(title="Выберите папку для сохранения")
        if dirname:
            var.set(dirname)

    def _change_theme(self, new_theme):
        self.settings["appearance_mode"] = new_theme
        save_settings(self.settings)
        self._apply_theme()

    def _save_settings(self, dialog):
        self.settings["output_dir"] = self.output_dir_var.get()
        self.settings["appearance_mode"] = self.theme_var.get()
        self.settings["youtube_quality"] = self.quality_var.get()
        save_settings(self.settings)
        self._apply_theme()
        dialog.destroy()
        logger.info("Настройки сохранены")


if __name__ == "__main__":
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    app = VideoStudioApp(root)
    root.mainloop()