# TTS_AI.py

print("Getting things ready, this may take a while...")

import torch
import tkinter as tk
from tkinter import scrolledtext, ttk
import sounddevice as sd
import numpy as np
import threading
import queue
import pyautogui
import time
import re
import keyboard
import os
import json 
import program

from options import OptionsWindow
import window_scanner 
from window_scanner import select_window_area

from TTS.api import TTS

from program import app_settings, save_config, toggle_renpy_mode

# --- Configuration ---
COMM_FILE = "tts_input.txt"
TRIGGER_FILE = "tts_trigger.txt"
CANCEL_FILE = "tts_cancel.txt"

# --- Delete COMM_FILE at Startup ---
try:
    if os.path.exists(COMM_FILE):
        os.remove(COMM_FILE)
        print(f"Cleaned up old communication file: {COMM_FILE}")
    if os.path.exists(CANCEL_FILE):
        os.remove(CANCEL_FILE)
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)

except Exception as e:
    print(f"Error deleting startup files: {e}")

# --- Globals and State Management ---
audio_queue = queue.Queue()
is_paused = False
is_cancelled = False
stream = None
chunk_size = 1024
last_read_normalized_text = ""

# --- Load Config on Startup ---
program.load_config()

# initialization - THIS IS THE ONLY PLACE THE MODEL IS NOW INITIALIZED AT STARTUP
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

DEFAULT_MODEL = "tts_models/en/vctk/vits"
DEFAULT_VOICE = "p243"
tts = TTS(DEFAULT_MODEL, progress_bar=False).to(device) # FIRST AND ONLY TTS() CALL HERE

VITS_ALLOWED_VOICES = ["p229", "p230", "p234", "p238", "p241", "p243", "p250", "p257", "p260"]

# Removed load_word_list and AllowedWords - now in window_scanner.py


# --- Text Processing Helpers ---

def normalize_text(text):
    """Cleans up text for reliable comparison."""
    if not text:
        return ""
    text = text.strip()
    text = ' '.join(text.split())
    return text

# Removed clean_text_content, is_text_valid, and preprocess_text


# --- Dedicated Speaker Function for File Triggers ---

def process_and_speak_on_trigger():
    """
    Reads the communication file (which contains text already cleaned/validated by the scanner),
    checks for the trigger, and initiates speech if new, valid text is found.
    """
    global last_read_normalized_text

    try:
        # 1. Check for cancel file and process it
        if os.path.exists(CANCEL_FILE):
            cancel_playback()
            last_read_normalized_text = ""
            os.remove(CANCEL_FILE)
            print(f"File-based cancellation processed. Guard reset.")
        
        # 2. Check for trigger file
        trigger_exists = os.path.exists(TRIGGER_FILE)
        
        # 3. Read the cleaned text from the scanner
        current_processed_text = ""
        if os.path.exists(COMM_FILE):
            with open(COMM_FILE, 'r', encoding='utf-8') as f:
                current_processed_text = f.read().strip()
        
        # 4. Handle found text (Text is already cleaned and validated by window_scanner.py)
        if current_processed_text:
            
            # Get normalized version for repetition check
            current_normalized_text = normalize_text(current_processed_text)

            # Check for repetition guard: clear guard if current text is the same
            if current_normalized_text and current_normalized_text == last_read_normalized_text:
                last_read_normalized_text = ""
                
            # Speak if it's new text (i.e., not a repeat and not empty)
            if current_normalized_text and current_normalized_text != last_read_normalized_text:
                print(f"Trigger detected. Speaking text: '{current_processed_text}'")
                text_box.delete("1.0", tk.END)
                text_box.insert("1.0", current_processed_text)
                speak_text_streaming(current_processed_text)
                last_read_normalized_text = current_normalized_text
        else:
             # If COMM_FILE is empty (meaning scanner found no valid text or timed out)
             if last_read_normalized_text:
                # Clear repetition guard and stop playback if something was currently speaking
                cancel_playback()
                last_read_normalized_text = ""
                text_box.delete("1.0", tk.END)


        # 5. Success! Remove the trigger if it existed.
        if trigger_exists and os.path.exists(TRIGGER_FILE):
            os.remove(TRIGGER_FILE)
            print(f"Removed trigger file: {TRIGGER_FILE}")
            
    except Exception as e:
        print(f"Error in process_and_speak_on_trigger: {e}")


# --- TTS and Audio Functions (Remain the same) ---
def load_model(model_name):
    global tts
    print(f"Loading model: {model_name}")
    tts = TTS(model_name, progress_bar=False).to(device)

    # Voices
    if hasattr(tts, "speakers") and tts.speakers:
        voices = list(tts.speakers)
        if "vctk" in model_name:
            voices = [v for v in voices if v in VITS_ALLOWED_VOICES]
    elif hasattr(tts, "speaker_manager") and tts.speaker_manager is not None:
        voices = tts.speaker_manager.speaker_ids
    else:
        voices = ["default"]

    # Languages
    if hasattr(tts, "languages") and tts.languages:
        languages = list(tts.languages)
    else:
        languages = ["default"]

    print("Voices available:", voices)
    print("Languages available:", languages)

    return voices, languages

def audio_callback(outdata, frames, time_, status):
    global audio_queue, is_paused, is_cancelled
    if status:
        # Filter underflow messages if they are excessive, or keep them for debugging audio issues
        if "underflow" not in str(status):
            print(status)
    outdata.fill(0)

    if is_cancelled:
        return

    if is_paused:
        return

    idx = 0
    while idx < frames:
        try:
            current_chunk = audio_queue.queue[0]
        except IndexError:
            break

        remaining = len(current_chunk)
        to_write = min(remaining, frames - idx)
        outdata[idx:idx + to_write, 0] = current_chunk[:to_write]
        if to_write < remaining:
            audio_queue.queue[0] = current_chunk[to_write:]
        else:
            audio_queue.get()
        idx += to_write

def start_stream():
    global stream
    if stream is None:
        stream = sd.OutputStream(
            samplerate=22050,
            channels=1,
            callback=audio_callback,
            blocksize=chunk_size
        )
        stream.start()

def stop_stream():
    global stream
    if stream:
        stream.stop()
        stream.close()
        stream = None

def speak_text_streaming(text_to_speak):
    """Accepts text and streams the TTS output."""
    global is_paused, is_cancelled, audio_queue

    if not text_to_speak:
        return

    sentences = re.split(r'(?<=[.!?]) +', text_to_speak)

    selected_model = model_var.get()
    selected_voice = voice_var.get()
    selected_lang = lang_var.get()

    with audio_queue.mutex:
        audio_queue.queue.clear()
    is_paused = False
    is_cancelled = False

    pause_button.config(text="Pause")
    start_stream()

    def tts_worker():
        for sentence in sentences:
            if is_cancelled:
                break
            kwargs = {}
            if selected_voice != "default":
                kwargs["speaker"] = selected_voice
            if selected_lang != "default":
                kwargs["language"] = selected_lang
            try:
                wav = tts.tts(text=sentence, **kwargs)
                audio_queue.put(np.array(wav, dtype=np.float32))
            except Exception as e:
                print(f"TTS generation error for sentence '{sentence}': {e}")
                break

        if not is_cancelled:
            while not audio_queue.empty():
                time.sleep(0.1)
            stop_stream()

        print("TTS generation finished.")

    threading.Thread(target=tts_worker, daemon=True).start()

def pause_resume():
    global is_paused
    is_paused = not is_paused
    pause_button.config(text="Resume" if is_paused else "Pause")

def cancel_playback():
    global is_cancelled
    is_cancelled = True
    with audio_queue.mutex:
        audio_queue.queue.clear()
    stop_stream()
    pause_button.config(text="Pause")
    print("Playback cancelled.")

# --- GUI and Settings Management ---

def save_settings_callback(new_settings):
    global app_settings
    old_speak_key = app_settings["speak_hotkey"]
    old_cancel_key = app_settings["cancel_hotkey"]

    try:
        keyboard.remove_hotkey(old_speak_key)
        keyboard.remove_hotkey(old_cancel_key)
    except:
        pass

    app_settings.update(new_settings)
    keyboard.add_hotkey(app_settings["speak_hotkey"], global_on_speak_key)
    keyboard.add_hotkey(app_settings["cancel_hotkey"], cancel_playback)
    renpy_mode_var.set(app_settings["renpy_mode"])
    save_config(app_settings)
    
    print(f"Hotkeys updated. Speak: '{app_settings['speak_hotkey']}', Cancel: '{app_settings['cancel_hotkey']}'")

def open_options():
    OptionsWindow(master=root, current_settings=app_settings, save_callback=save_settings_callback)

root = tk.Tk()
root.title("Text-to-Speech")

# Dark theme colors
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
BTN_SCAN = "#007bff"
BTN_GREEN = "#2e8b57"
BTN_OPTIONS = "#6a5acd"
BTN_ORANGE = "#cc8400"
BTN_RED = "#b22222"
ENTRY_BG = "#2d2d2d"

root.configure(bg=BG_COLOR)

text_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=15,
                                     font=("Arial", 12), bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white")
text_box.pack(padx=10, pady=10)

# --- Dropdowns ---
dropdowns_frame = tk.Frame(root, bg=BG_COLOR)
dropdowns_frame.pack(pady=10)

model_frame = tk.Frame(dropdowns_frame, bg=BG_COLOR)
model_frame.grid(row=0, column=0, padx=10)
tk.Label(model_frame, text="Select Model:", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 10)).pack()
model_var = tk.StringVar(value=DEFAULT_MODEL)
model_dropdown = ttk.Combobox(model_frame, textvariable=model_var,
                              values=[
                                  "tts_models/en/ljspeech/tacotron2-DDC",
                                  "tts_models/en/vctk/vits",
                                  "tts_models/multilingual/multi-dataset/your_tts"
                              ],
                              state="readonly", font=("Arial", 10))
model_dropdown.pack()

voice_frame = tk.Frame(dropdowns_frame, bg=BG_COLOR)
voice_frame.grid(row=0, column=1, padx=10)
tk.Label(voice_frame, text="Select Voice:", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 10)).pack()
voice_var = tk.StringVar(value=DEFAULT_VOICE)
voice_dropdown = ttk.Combobox(voice_frame, textvariable=voice_var,
                              values=[DEFAULT_VOICE], state="readonly", font=("Arial", 10))
voice_dropdown.pack()

lang_frame = tk.Frame(dropdowns_frame, bg=BG_COLOR)
lang_frame.grid(row=0, column=2, padx=10)
tk.Label(lang_frame, text="Select Language:", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 10)).pack()
lang_var = tk.StringVar(value="default")
lang_dropdown = ttk.Combobox(lang_frame, textvariable=lang_var,
                             values=["default"], state="readonly", font=("Arial", 10))
lang_dropdown.pack()

def update_model(event=None):
    # This function is now correctly used only when a NEW model is selected in the dropdown
    voices, languages = load_model(model_var.get())
    voice_dropdown["values"] = voices
    if model_var.get() == DEFAULT_MODEL and DEFAULT_VOICE in voices:
        voice_var.set(DEFAULT_VOICE)
    elif voices:
        voice_var.set(voices[0])
    else:
        voice_var.set("default")
    lang_dropdown["values"] = languages
    lang_var.set(languages[0])

model_dropdown.bind("<<ComboboxSelected>>", update_model)

# --- Action Buttons ---
action_buttons_frame = tk.Frame(root, bg=BG_COLOR)
action_buttons_frame.pack(pady=5)

options_button = tk.Button(action_buttons_frame, text="Options", command=open_options,
                         font=("Arial", 12), bg=BTN_OPTIONS, fg="white", relief="flat", width=10)
options_button.pack(side=tk.LEFT, padx=5)

# Updated helper for Speak button to handle None safely
def manual_speak():
    # Write text from box to comm file to use the full processing pipeline
    text_from_box = text_box.get("1.0", tk.END).strip()
    if text_from_box:
        # Note: If manual text is entered here, it bypasses the cleaning/validation of the scanner.
        # This is expected for manual input.
        with open(COMM_FILE, 'w', encoding='utf-8') as f:
            f.write(text_from_box)
        
        # Explicitly call the process function
        threading.Thread(target=process_and_speak_on_trigger, daemon=True).start()
    else:
        cancel_playback()
        last_read_normalized_text = ""
        text_box.delete("1.0", tk.END)


speak_button = tk.Button(action_buttons_frame, text="Speak", command=manual_speak,
                         font=("Arial", 12), bg=BTN_GREEN, fg="white", relief="flat", width=10)
speak_button.pack(side=tk.LEFT, padx=5)

pause_button = tk.Button(action_buttons_frame, text="Pause", command=pause_resume,
                         font=("Arial", 12), bg=BTN_ORANGE, fg="white", relief="flat", width=10)
pause_button.pack(side=tk.LEFT, padx=5)

cancel_button = tk.Button(action_buttons_frame, text="Cancel", command=cancel_playback,
                          font=("Arial", 12), bg=BTN_RED, fg="white", relief="flat", width=10)
cancel_button.pack(side=tk.LEFT, padx=5)

# --- Utility Buttons ---
utility_buttons_frame = tk.Frame(root, bg=BG_COLOR)
utility_buttons_frame.pack(pady=10)

def clear_text():
    text_box.delete("1.0", tk.END)

def paste_text():
    try:
        clipboard_content = root.clipboard_get()
        
        # Write to COMM_FILE and explicitly trigger the processing
        # Note: This text is NOT cleaned/validated.
        with open(COMM_FILE, 'w', encoding='utf-8') as f:
            f.write(clipboard_content)
            
        threading.Thread(target=process_and_speak_on_trigger, daemon=True).start()

    except tk.TclError:
        pass

scan_button = tk.Button(utility_buttons_frame, text="Scan", command=select_window_area,
                         font=("Arial", 12), bg=BTN_SCAN, fg="white", relief="flat", width=10)
scan_button.pack(side=tk.LEFT, padx=5)

clear_button = tk.Button(utility_buttons_frame, text="Clear", command=clear_text,
                         font=("Arial", 12), bg="#444444", fg="white", relief="flat", width=10)
clear_button.pack(side=tk.LEFT, padx=5)

paste_button = tk.Button(utility_buttons_frame, text="Paste", command=paste_text,
                         font=("Arial", 12), bg="#555555", fg="white", relief="flat", width=10)
paste_button.pack(side=tk.LEFT, padx=5)

# --- Renpy Mode Checkbox ---
renpy_frame = tk.Frame(root, bg=BG_COLOR)
renpy_frame.pack(side=tk.LEFT, padx=10, pady=(0, 10), anchor='sw')

renpy_mode_var = tk.BooleanVar(value=app_settings["renpy_mode"])
renpy_mode_check = tk.Checkbutton(renpy_frame, text="Renpy Mode", variable=renpy_mode_var,
                                  bg=BG_COLOR, fg=FG_COLOR, selectcolor=ENTRY_BG,
                                  font=("Arial", 10), relief="flat",
                                  command=toggle_renpy_mode)
renpy_mode_check.pack(side=tk.LEFT, padx=10)


# Initialize (FIX IMPLEMENTED HERE: Removed the redundant update_model() call)
# Instead of calling update_model(), we directly set the initial dropdown values 
# from the already loaded global 'tts' object.

# Voices
if hasattr(tts, "speakers") and tts.speakers:
    initial_voices = list(tts.speakers)
    if "vctk" in DEFAULT_MODEL:
        initial_voices = [v for v in initial_voices if v in VITS_ALLOWED_VOICES]
elif hasattr(tts, "speaker_manager") and tts.speaker_manager is not None:
    initial_voices = tts.speaker_manager.speaker_ids
else:
    initial_voices = ["default"]

# Languages
if hasattr(tts, "languages") and tts.languages:
    initial_languages = list(tts.languages)
else:
    initial_languages = ["default"]

voice_dropdown["values"] = initial_voices
# Ensure the default voice is set if it's available
if DEFAULT_VOICE in initial_voices:
    voice_var.set(DEFAULT_VOICE)
elif initial_voices:
    voice_var.set(initial_voices[0])
else:
    voice_var.set("default")
    
lang_dropdown["values"] = initial_languages
lang_var.set(initial_languages[0])

print("Voices available:", initial_voices)
print("Languages available:", initial_languages)


# --- Hotkey Functions ---
def global_on_speak_key():
    """
    Called by the 'speak_hotkey' (usually Ctrl+C).
    It copies, writes the text to the COMM_FILE, and explicitly triggers processing.
    """
    try:
        cancel_playback()
        # Assume the hotkey itself (e.g., Ctrl+C) handles the copy action.
        time.sleep(0.1)

        clipboard_content = root.clipboard_get()

        # Write the clipboard text to the communication file
        # Note: This text is NOT cleaned/validated.
        with open(COMM_FILE, 'w', encoding='utf-8') as f:
            f.write(clipboard_content)
        
        # Then, manually call the process function in a new thread
        threading.Thread(target=process_and_speak_on_trigger, daemon=True).start()


    except Exception as e:
        print("Error copying selected text:", e)

keyboard.add_hotkey(app_settings["speak_hotkey"], global_on_speak_key)
keyboard.add_hotkey(app_settings["cancel_hotkey"], cancel_playback)

# --- File Watching Logic (Minimal Check) ---

def minimal_trigger_check():
    """
    Minimal polling check for the trigger file existence.
    Scheduled at a low frequency (e.g., 500ms) to avoid lag while enabling 
    inter-process communication from the scanner.
    """
    # CRITICAL: This is the ONLY polling/loop in the program now. It is lightweight.
    
    # 1. Check for trigger file
    if os.path.exists(TRIGGER_FILE):
        # Trigger found, start the heavy work in a separate thread
        # The thread will check for the cancel file, process the text, and remove the trigger file.
        print("Minimal check detected trigger. Starting speech process...")
        threading.Thread(target=process_and_speak_on_trigger, daemon=True).start()

    # 2. Reschedule the check (500ms is half a second, very lightweight)
    root.after(500, minimal_trigger_check)


# Start the minimal trigger check loop
root.after(500, minimal_trigger_check) # <--- ADDED LINE: Start the periodic check
root.mainloop()