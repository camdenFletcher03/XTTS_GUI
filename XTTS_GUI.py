import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import requests
import simpleaudio as sa
import io
import os
from pydub import AudioSegment

# This program is designed to provide a graphical user interface for the xtts_api_server project: https://github.com/daswer123/xtts-api-server

class XTTS_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("XTTS GUI")
        self.root.geometry("500x500")

        # Defaults
        self.base_url = tk.StringVar(value="http://localhost:8020")
        self.voice = tk.StringVar(value="None")
        self.voice_map = {"default": {"voice_id": "default", "preview_url": ""}}
        self.language_map = {}  # name -> code

        # Notebook (for tabs)
        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Text-to-Speech Tab
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

        # Settings Tab
        settings_frame = tk.Frame(notebook)
        notebook.add(settings_frame, text="XTTS Settings")

        tk.Label(settings_frame, text="XTTS Base URL:").pack(anchor="w", padx=10, pady=(15, 5))
        self.url_entry = tk.Entry(settings_frame, textvariable=self.base_url, width=60)
        self.url_entry.pack(padx=10, pady=5)

        tk.Label(settings_frame, text="Select Voice:").pack(anchor="w", padx=10, pady=(15, 5))
        self.voice_dropdown = ttk.Combobox(
            settings_frame,
            textvariable=self.voice,
            values=list(self.voice_map.keys()),
            state="readonly"
        )
        self.voice_dropdown.pack(padx=10, pady=5)
        self.voice_dropdown.bind("<<ComboboxSelected>>", self.on_voice_select)

        tk.Label(settings_frame, text="Select Language:").pack(anchor="w", padx=10, pady=(15, 5))
        self.language = tk.StringVar(value="en")
        self.language_dropdown = ttk.Combobox(
            settings_frame,
            textvariable=self.language,
            values=[],
            state="readonly"
        )
        self.language_dropdown.pack(padx=10, pady=5)

        btn_settings = tk.Frame(settings_frame)
        btn_settings.pack(pady=10)

        self.refresh_btn = tk.Button(btn_settings, text="Refresh", command=self.refresh_options)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

        self.preview_btn = tk.Button(btn_settings, text="Preview Voice", command=self.preview_voice)
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        # Load languages and voices from server
        self.refresh_options()

    # -- Support functions --

    # Logging helper
    def notification_log(self, prefix, msg):
        print(f"[{prefix}]: {msg}")
        messagebox.showinfo(prefix, msg)
        
    # Play audio from bytes
    def play_audio_bytes(self, audio_bytes, mime_type="audio/wav"):
        try:
            fmt = self.set_file_type(mime_type)
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            audio = audio.set_frame_rate(44100).set_channels(2).set_sample_width(2)
            raw = audio.raw_data
            wave_obj = sa.WaveObject(
                raw,
                num_channels=audio.channels,
                bytes_per_sample=audio.sample_width,
                sample_rate=audio.frame_rate,
            )
            play_obj = wave_obj.play()
            play_obj.wait_done()
        except Exception as e:
            self.notification_log("Error", f"Playback failed:\n{e}")

    def get_tts_audio(self, text):
        if not text:
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
                "language": lang_code
            }
            print("[TTS Payload]: ", str(payload))
            url = f"{self.base_url.get().rstrip('/')}/tts_to_audio/"
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                return r.content, r.headers.get("Content-Type", "audio/wav")
            else:
                self.notification_log("Error", f"XTTS server error:\n{r.text}")
                return None, None
        except Exception as e:
            self.notification_log("Error", f"{e}")
            return None, None

    def set_file_type(self, mime_type):
        return "mp3" if "mp3" in mime_type or "mpeg" in mime_type else "wav"
    
    def read_aloud(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            self.notification_log("Warning", "Please enter some text.")
            return
        audio_data, ctype = self.get_tts_audio(text)
        if audio_data:
            self.play_audio_bytes(audio_data, mime_type=ctype)

    def save_audio(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            self.notification_log("Warning", "Please enter some text.")
            return

        audio_data, ctype = self.get_tts_audio(text)
        if not audio_data:
            return

        # Determine format from TTS output
        fmt = self.set_file_type(ctype)
        ext = f".{fmt}"

        # Ask user for save location and filename with appropriate extension
        filepath = filedialog.asksaveasfilename(
            title="Save Audio File",
            defaultextension=ext,
            filetypes=[(f"{fmt.upper()} files", f"*{ext}")]
        )
        if not filepath:
            return

        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=fmt)
            audio.export(filepath, format=fmt)
            self.notification_log("Saved", f"Audio saved to:\n{filepath}")
        except Exception as e:
            self.notification_log("Error", f"Could not save file:\n{e}")

    def refresh_options(self):
        self.refresh_languages()
        self.refresh_voices()

    # Load available voices from /speakers
    def refresh_voices(self):
        try:
            url = f"{self.base_url.get().rstrip('/')}/speakers"
            response = requests.get(url)
            if response.status_code == 200:
                speakers = response.json()
                self.voice_map = {}
                for s in speakers:
                    preview_url = s.get("preview_url", "")
                    if preview_url and not preview_url.startswith("http"):
                        preview_url = f"{self.base_url.get().rstrip('/')}/{preview_url.lstrip('/')}"
                    self.voice_map[s["name"]] = {
                        "voice_id": s["voice_id"],
                        "preview_url": preview_url
                    }
                self.voice_dropdown["values"] = list(self.voice_map.keys())
                if self.voice_map:
                    self.voice.set(list(self.voice_map.keys())[0])
                print(f"Available voices loaded from server: {list(self.voice_map.keys())}")
            else:
                self.notification_log("Error", f"Failed to fetch voices:\n{response.text}")
        except Exception as e:
            self.notification_log("Error", f"Could not connect to XTTS server:\n{e}")
    
    # Load available languages from /languages
    def refresh_languages(self):
        try:
            url = f"{self.base_url.get().rstrip('/')}/languages"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                self.language_map = data.get("languages", {})
                lang_names = list(self.language_map.keys())
                self.language_dropdown["values"] = lang_names
                if "English" in self.language_map:
                    self.language.set("English")
                elif lang_names:
                    self.language.set(lang_names[0])

                print(f"Supported languages loaded from server: {lang_names}")
            else:
                self.notification_log("Error", f"Failed to load languages:\n{response.text}")
        except Exception as e:
            self.notification_log("Error", f"Could not connect to XTTS server:\n{e}")

    def preview_voice(self):
        selected_name = self.voice.get()
        voice_info = self.voice_map.get(selected_name)
        if not voice_info:
            self.notification_log("Warning", "No voice selected.")
            return
        try:
            audio_data, ctype = self.get_tts_audio("test")
            if audio_data:
                self.play_audio_bytes(audio_data, mime_type=ctype)
            else:
                self.notification_log("Error", "Failed to generate preview audio.")
        except Exception as e:
            self.notification_log("Error", f"Could not play preview:\n{e}")

    def on_voice_select(self, event):
        selected = self.voice.get()
        print(f"[Voice Selection]: Speaker '{selected}' chosen from list.")

if __name__ == "__main__":
    root = tk.Tk()
    app = XTTS_GUI(root)
    root.mainloop()
