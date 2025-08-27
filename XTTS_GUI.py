import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import requests
import simpleaudio as sa
import io
import os
from pydub import AudioSegment
import re
import threading

# This program is designed to provide a graphical user interface for the xtts_api_server project: https://github.com/daswer123/xtts-api-server

class XTTS_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("XTTS GUI")
        self.root.geometry("500x500")
        self.root.resizable(False, False)  

        # Defaults
        self.base_url = tk.StringVar(value="http://localhost:8020")
        self.voice = tk.StringVar(value="None")
        self.voice_map = {"default": {"voice_id": "default", "preview_url": ""}}
        self.language_map = {}
        self.split_by_sentences = tk.BooleanVar(value=True)
        self.cancel_batch = threading.Event()  

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)

        # --- TTS Tab ---
        tts_frame = tk.Frame(notebook)
        notebook.add(tts_frame, text="Text to Speech")

        self.textbox = scrolledtext.ScrolledText(tts_frame, wrap=tk.WORD, width=70, height=15)
        self.textbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(tts_frame)
        btn_frame.pack(pady=10)

        self.read_btn = tk.Button(btn_frame, text="Read Aloud", command=self.read_aloud)
        self.read_btn.pack(side=tk.LEFT, padx=5)

        self.save_btn = tk.Button(btn_frame, text="Save Audio", command=self.save_audio)
        self.save_btn.pack(side=tk.LEFT, padx=5)

        # --- Batch TTS Tab ---
        batch_frame = tk.Frame(notebook)
        notebook.add(batch_frame, text="Batch TTS")

        tk.Label(batch_frame, text="Convert .txt to TTS audio by splitting into parts and merging.").grid(
            row=0, column=0, columnspan=3, pady=10
        )

        self.selected_file = tk.StringVar()
        self.selected_folder = tk.StringVar()
        self.cleanup_temp = tk.BooleanVar(value=True)
        self.split_by_sentences = tk.BooleanVar(value=True)

        tk.Entry(batch_frame, textvariable=self.selected_file, width=50).grid(
            row=1, column=0, padx=5, pady=5, sticky="ew"
        )
        tk.Button(batch_frame, text="Browse File", command=self.browse_file, width=15).grid(
            row=1, column=1, padx=5, pady=5
        )

        tk.Entry(batch_frame, textvariable=self.selected_folder, width=50).grid(
            row=2, column=0, padx=5, pady=5, sticky="ew"
        )
        tk.Button(batch_frame, text="Browse Folder", command=self.browse_folder, width=15).grid(
            row=2, column=1, padx=5, pady=5
        )

        self.cleanup_check = tk.Checkbutton(
            batch_frame, text="Remove individual part files after merge", variable=self.cleanup_temp
        )
        self.cleanup_check.grid(row=3, column=0, columnspan=2, pady=5, sticky="w")

        self.split_check = tk.Checkbutton(
            batch_frame, text="Split by sentences (uncheck = split by lines)", variable=self.split_by_sentences
        )
        self.split_check.grid(row=4, column=0, columnspan=2, pady=5, sticky="w")

        btns = tk.Frame(batch_frame)
        btns.grid(row=5, column=0, columnspan=2, pady=20)

        self.batch_btn = tk.Button(btns, text="Generate Audio", command=self.batch_generate, width=15)
        self.batch_btn.pack(side=tk.LEFT, padx=10)

        self.cancel_btn = tk.Button(btns, text="Cancel", command=self.cancel_processing, state="disabled", width=15)
        self.cancel_btn.pack(side=tk.LEFT, padx=10)

        self.progress = tk.Label(batch_frame, text="")
        self.progress.grid(row=6, column=0, columnspan=2, pady=10)

        batch_frame.grid_columnconfigure(0, weight=1)

        # --- Settings Tab ---
        settings_frame = tk.Frame(notebook)
        notebook.add(settings_frame, text="XTTS Settings")

        tk.Label(settings_frame, text="XTTS Base URL:").pack(anchor="w", padx=10, pady=(15, 5))
        self.url_entry = tk.Entry(settings_frame, textvariable=self.base_url, width=60)
        self.url_entry.pack(padx=10, pady=5)

        tk.Label(settings_frame, text="Select Voice:").pack(anchor="w", padx=10, pady=(15, 5))
        self.voice_dropdown = ttk.Combobox(
            settings_frame, textvariable=self.voice, values=list(self.voice_map.keys()), state="readonly"
        )
        self.voice_dropdown.pack(padx=10, pady=5)
        self.voice_dropdown.bind("<<ComboboxSelected>>", self.on_voice_select)

        tk.Label(settings_frame, text="Select Language:").pack(anchor="w", padx=10, pady=(15, 5))
        self.language = tk.StringVar(value="en")
        self.language_dropdown = ttk.Combobox(settings_frame, textvariable=self.language, values=[], state="readonly")
        self.language_dropdown.pack(padx=10, pady=5)

        btn_settings = tk.Frame(settings_frame)
        btn_settings.pack(pady=10)

        self.refresh_btn = tk.Button(btn_settings, text="Refresh", command=self.refresh_options)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.preview_btn = tk.Button(btn_settings, text="Preview Voice", command=self.preview_voice)
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        self.refresh_options()

    # --- Utility ---
    def notification_log(self, prefix, msg):
        print(f"[{prefix}]: {msg}")
        messagebox.showinfo(prefix, msg)

    def set_file_type(self, mime_type):
        return "mp3" if "mp3" in mime_type or "mpeg" in mime_type else "wav"

    def run_in_thread(self, func, *args):
        threading.Thread(target=func, args=args, daemon=True).start()

    def with_button_disabled(self, buttons, func):
        if not isinstance(buttons, (list, tuple)):
            buttons = [buttons]

        def wrapper():
            for btn in buttons:
                self.root.after(0, lambda b=btn: b.config(state="disabled"))
            try:
                func()
            finally:
                for btn in buttons:
                    self.root.after(0, lambda b=btn: b.config(state="normal"))
        return wrapper

    # --- Core TTS ---
    def get_tts_audio(self, text):
        if not text.strip():
            return None, None
        v = self.voice.get()
        if not v:
            self.notification_log("No Voice Selected", "Please select a voice.")
            return None, None
        try:
            voice_info = self.voice_map[v]
            lang_code = self.language_map.get(self.language.get(), "en")

            payload = {
                "text": text,
                "voice_id": voice_info["voice_id"],
                "speaker_wav": f"{voice_info['voice_id']}.wav",
                "language": lang_code,
            }

            url = f"{self.base_url.get().rstrip('/')}/tts_to_audio/"
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                return r.content, r.headers.get("Content-Type", "audio/wav")
            else:
                self.notification_log("Error", f"XTTS server error:\n{r.text}")

        except Exception as e:
            self.notification_log("Error", f"{e}")
        return None, None

    def read_aloud(self):
        text = self.textbox.get("1.0", tk.END).strip()

        def task():
            audio_data, ctype = self.get_tts_audio(text)
            if audio_data:
                self.root.after(0, lambda: self.play_audio_bytes(audio_data, mime_type=ctype))

        self.run_in_thread(self.with_button_disabled([self.read_btn, self.save_btn], task))

    def save_audio(self):
        text = self.textbox.get("1.0", tk.END).strip()

        def task():
            audio_data, ctype = self.get_tts_audio(text)
            if not audio_data:
                return
            fmt = self.set_file_type(ctype)
            filepath = filedialog.asksaveasfilename(
                defaultextension=f".{fmt}", filetypes=[(f"{fmt.upper()} files", f"*.{fmt}")]
            )
            if not filepath:
                return
            try:
                audio = AudioSegment.from_file(io.BytesIO(audio_data), format=fmt)
                audio.export(filepath, format=fmt)
                self.root.after(0, lambda: self.notification_log("Saved", f"Audio saved to:\n{filepath}"))
            except Exception as e:
                self.root.after(0, lambda: self.notification_log("Error", f"Could not save file:\n{e}"))

        self.run_in_thread(self.with_button_disabled([self.read_btn, self.save_btn], task))

    def play_audio_bytes(self, audio_bytes, mime_type="audio/wav"):
        try:
            fmt = self.set_file_type(mime_type)
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            audio = audio.set_frame_rate(44100).set_channels(2).set_sample_width(2)
            raw = audio.raw_data
            wave_obj = sa.WaveObject(
                raw, num_channels=audio.channels, bytes_per_sample=audio.sample_width, sample_rate=audio.frame_rate
            )
            play_obj = wave_obj.play()
            play_obj.wait_done()
        except Exception as e:
            self.notification_log("Error", f"Playback failed:\n{e}")

    # --- Batch TTS ---
    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.selected_file.set(file_path)

    def browse_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.selected_folder.set(folder_path)

    def extract_sentences(self, filepath, split_by_sentences=True):
        with open(filepath, "r", encoding="utf-8") as f:
            text_content = f.read()
        if split_by_sentences:
            parts = re.split(r'(?<=[.!?])\s+', text_content)
        else:
            parts = text_content.splitlines()
        return [s.strip() for s in parts if s.strip()]

    def cancel_processing(self):
        self.cancel_batch.set()

    def batch_generate(self):
        def task():
            self.cancel_batch.clear()
            self.root.after(0, lambda: self.cancel_btn.config(state="normal"))

            infile, outdir = self.selected_file.get(), self.selected_folder.get()
            if not infile or not os.path.isfile(infile):
                self.root.after(0, lambda: self.notification_log("Error", "Please select a valid text file."))
                self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
                return
            if not outdir or not os.path.isdir(outdir):
                self.root.after(0, lambda: self.notification_log("Error", "Please select a valid output folder."))
                self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
                return

            temp_dir = os.path.join(outdir, "parts")
            os.makedirs(temp_dir, exist_ok=True)

            parts = self.extract_sentences(infile, split_by_sentences=self.split_by_sentences.get())
            total = len(parts)
            merged_audio = AudioSegment.silent(duration=0)
            fmt = "wav"

            for i, part in enumerate(parts, 1):
                if self.cancel_batch.is_set():
                    self.root.after(0, lambda: self.progress.config(text="Batch cancelled."))
                    self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
                    return

                self.root.after(0, lambda i=i, total=total: self.progress.config(text=f"Processing part {i}/{total}..."))
                audio_data, ctype = self.get_tts_audio(part)
                if not audio_data:
                    continue
                fmt = self.set_file_type(ctype)
                filename = os.path.join(temp_dir, f"part_{i:04d}.{fmt}")
                try:
                    audio = AudioSegment.from_file(io.BytesIO(audio_data), format=fmt)
                    audio.export(filename, format=fmt)
                    merged_audio += audio
                except Exception as e:
                    self.root.after(0, lambda i=i, e=e: self.notification_log("Error", f"Could not save part {i}:\n{e}"))

            merged_path = os.path.join(outdir, f"{os.path.splitext(os.path.basename(infile))[0]}.{fmt}")
            merged_audio.export(merged_path, format=fmt)

            if self.cleanup_temp.get():
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)

            self.root.after(0, lambda: self.progress.config(text="Batch TTS complete!"))
            self.root.after(0, lambda: self.notification_log("Done", f"Generated {total} parts.\nMerged file: {merged_path}"))
            self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))

        self.run_in_thread(self.with_button_disabled(self.batch_btn, task))

    # --- Server Info ---
    def refresh_options(self):
        self.run_in_thread(self.refresh_languages)
        self.run_in_thread(self.refresh_voices)

    def refresh_voices(self):
        try:
            url = f"{self.base_url.get().rstrip('/')}/speakers"
            r = requests.get(url)
            if r.status_code == 200:
                speakers = r.json()
                self.voice_map = {
                    s["name"]: {"voice_id": s["voice_id"], "preview_url": s.get("preview_url", "")} for s in speakers
                }
                self.root.after(0, lambda: self.voice_dropdown.configure(values=list(self.voice_map.keys())))
                if self.voice_map:
                    self.root.after(0, lambda: self.voice.set(list(self.voice_map.keys())[0]))
            else:
                self.root.after(0, lambda: self.notification_log("Error", f"Failed to fetch voices:\n{r.text}"))
        except Exception as e:
            self.root.after(0, lambda: self.notification_log("Error", f"Could not connect to XTTS server:\n{e}"))

    def refresh_languages(self):
        try:
            url = f"{self.base_url.get().rstrip('/')}/languages"
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()
                self.language_map = data.get("languages", {})
                langs = list(self.language_map.keys())
                self.root.after(0, lambda: self.language_dropdown.configure(values=langs))
                if "English" in self.language_map:
                    self.root.after(0, lambda: self.language.set("English"))
                elif langs:
                    self.root.after(0, lambda: self.language.set(langs[0]))
            else:
                self.root.after(0, lambda: self.notification_log("Error", f"Failed to fetch languages:\n{r.text}"))
        except Exception as e:
            self.root.after(0, lambda: self.notification_log("Error", f"Could not connect to XTTS server:\n{e}"))

    def preview_voice(self):
        def task():
            audio_data, ctype = self.get_tts_audio("test")
            if audio_data:
                self.root.after(0, lambda: self.play_audio_bytes(audio_data, mime_type=ctype))

        self.run_in_thread(self.with_button_disabled(self.preview_btn, task))

    def on_voice_select(self, event):
        print(f"[Voice Selection]: {self.voice.get()}")

if __name__ == "__main__":
    root = tk.Tk()
    app = XTTS_GUI(root)
    root.mainloop()
