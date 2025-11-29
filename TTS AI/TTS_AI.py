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
import json # Import JSON library for file persistence
import program

from options import OptionsWindow
from window_scanner import select_window_area

from TTS.api import TTS

from program import app_settings, save_config, toggle_renpy_mode

# --- Configuration ---
COMM_FILE = "tts_input.txt"
TRIGGER_FILE = "tts_trigger.txt"
CANCEL_FILE = "tts_cancel.txt"    # ADDED: Dedicated file for reliable cancellation

# --- Delete COMM_FILE at Startup ---
try:
    if os.path.exists(COMM_FILE):
        os.remove(COMM_FILE)
        print(f"Cleaned up old communication file: {COMM_FILE}")
    # Also clean up CANCEL_FILE and TRIGGER_FILE on startup for a fresh start
    if os.path.exists(CANCEL_FILE):
        os.remove(CANCEL_FILE)
    if os.path.exists(TRIGGER_FILE):
        os.remove(TRIGGER_FILE)

except Exception as e:
    # Log any unexpected error during deletion
    print(f"Error deleting startup files: {e}")
# -----------------------------------------------

# --- Globals and State Management ---
audio_queue = queue.Queue()
is_paused = False
is_cancelled = False
stream = None
chunk_size = 1024
last_read_normalized_text = ""

# --- Load Config on Startup ---
program.load_config()
# ------------------------------

# initialization
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

DEFAULT_MODEL = "tts_models/en/vctk/vits"

DEFAULT_VOICE = "p243"
tts = TTS(DEFAULT_MODEL, progress_bar=False).to(device)

VITS_ALLOWED_VOICES = ["p229", "p230", "p234", "p238", "p241", "p243", "p250", "p257", "p260"]


# --- Text Preprocessing ---
def normalize_text(text):
    """
    Cleans up text for reliable comparison, preventing silent failures
    due to minor whitespace/newline differences.
    """
    if not text:
        return ""
    text = text.strip()
    text = ' '.join(text.split())
    return text

def preprocess_text(text):
    """
    Preprocess TTS input text for natural TTS.
    """
    # Renpy Mode Preprocessing - now checks app_settings directly
    if app_settings["renpy_mode"]:
        # *** NEW: Remove all line breaks and replace with a space ***
        text = text.replace('\n', ' ')

        # 1. Remove character name prefixes
        text = re.sub(r'^\s*".*?"\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[^:]+:\s*', '', text, flags=re.MULTILINE)
        text = text.strip()

        # 2. Convert pipe symbol to 'I'
        text = text.replace("|", "I")
        text = text.replace("$", "s")


    # ... (Preprocess logic remains the same)

    # Step 0: normalize line breaks into sentence breaks
    # This block is now slightly redundant for RenPy mode, but harmless,
    # as the previous step removes all \n and replaces them with a space.
    lines = text.splitlines()
    normalized_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Only add a period if the line doesn't end in punctuation or a letter
        if not re.search(r'[.!?]$', line) and re.search(r'[a-zA-Z0-9]', line):
             line += '.'
        normalized_lines.append(line)
    text = " ".join(normalized_lines)

    # Step 1: remove tildes
    text = text.replace("~", "")

    # Step 2: replace 'Ooh' with 'Oh'
    text = re.sub(r'\bOoh\b', 'Oh', text, flags=re.IGNORECASE)

    # Step 3: replace fractions
    fraction_map = {
        '¼': 'a quarter',
        '½': 'a half',
        '¾': 'three quarters'
    }
    for k, v in fraction_map.items():
        text = text.replace(k, v)

    # Step 4: replace 'oz' with 'ounces' everywhere
    text = re.sub(r'oz', 'ounces', text, flags=re.IGNORECASE)

    # Step 5: collapse repeated letters at start of words
    def collapse_repeats(match):
        first_letter = match.group(1)
        rest = match.group(2) if match.group(2) else ""
        return first_letter + rest
    text = re.sub(r'\b(\w)(\1+)?', collapse_repeats, text)
    text = re.sub(r'\b[A-Za-z]-', '', text)

    # Step 6: replace single-letter vocalizations
    vocalizations = {
        "A": "Ah",
        "O": "Oh",
        "H": "Hhh",
        "E": "Ehh",
        "U": "Uhh",
    }
    def replace_vocal(match):
        word = match.group(0)
        return vocalizations.get(word, word)
    text = re.sub(r'\b[A-Z]\b', replace_vocal, text)

    # Step 7: skip unwanted vocalizations (m, mm, mmm)
    text = re.sub(r'\b[mM]{1,3}\b', '', text)

    # Step 7.5: collapse multiple periods into a single one
    text = re.sub(r'\.{2,}', '.', text)

    # Step 8: skip standalone punctuation
    text = re.sub(r'\b[.,!?]\b', '', text)

    # Remove extra spaces created by removals
    text = re.sub(r'\s+', ' ', text).strip()

    text = re.sub(r'\*', '', text)

    return text

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

    # --- FIX 1: REMOVED internal call to preprocess_text() ---
    # Caller functions (file_watcher and global_on_speak_key) now provide pre-processed text.
    # text_to_speak = preprocess_text(text_to_speak)

    if not text_to_speak:
        return

    sentences = re.split(r'(?<=[.!?]) +', text_to_speak)

    selected_model = model_var.get()
    selected_voice = voice_var.get()
    selected_lang = lang_var.get()

    # Reset
    with audio_queue.mutex:
        audio_queue.queue.clear()
    is_paused = False
    is_cancelled = False

    # Update pause button state immediately
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

        # Stop the stream if it hasn't been cancelled manually
        if not is_cancelled:
            # Wait for the queue to empty before stopping the stream
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

# --- File Watching Logic ---
def file_watcher():
    """Continuously checks the communication files for trigger and text updates."""
    global last_read_normalized_text

    try:
        # --- NEW: Check for dedicated Cancel File (Inter-Process Communication) ---
        if os.path.exists(CANCEL_FILE):
            cancel_playback()
            # CRITICAL: Reset the guard after cancellation to ensure the next scan speaks
            last_read_normalized_text = ""
            os.remove(CANCEL_FILE)
            print(f"File-based cancellation processed. Guard reset.")
        # ---------------------------------------------

        current_raw_text = ""

        # 1. Read raw text from the file (if it exists)
        if os.path.exists(COMM_FILE):
            with open(COMM_FILE, 'r', encoding='utf-8') as f:
                current_raw_text = f.read().strip()

        # --- FIX 3A: Preprocess the raw text to get the version for TTS and display ---
        current_processed_text = preprocess_text(current_raw_text)
        # --- End FIX 3A ---

        # The normalized text (used for the speech guard) should be based on the processed text.
        current_normalized_text = normalize_text(current_processed_text)

        # 2. Check for the manual trigger file
        trigger_exists = os.path.exists(TRIGGER_FILE)

        # 3. Handle Speaking ONLY if trigger exists
        if trigger_exists:
            try:
                # If the current text is the same as the last spoken text,
                # we clear the guard to force a respeak (allowing repetition on trigger).
                if current_normalized_text and current_normalized_text == last_read_normalized_text:
                    last_read_normalized_text = ""

                # Speak only if the text is genuinely new OR the guard was just cleared
                if current_normalized_text and current_normalized_text != last_read_normalized_text:

                    print(f"Trigger detected. Speaking text: '{current_raw_text}'")

                    # Update the local GUI textbox
                    text_box.delete("1.0", tk.END)
                    # --- FIX 3B: Insert the PROCESSED text ---
                    text_box.insert("1.0", current_processed_text)

                    # Speak the new text
                    # --- FIX 3C: Speak the PROCESSED text ---
                    speak_text_streaming(current_processed_text)

                    # Update the tracking variable with the normalized text
                    last_read_normalized_text = current_normalized_text

                # CRITICAL: Remove the trigger file after processing
                os.remove(TRIGGER_FILE)
                print(f"Removed trigger file: {TRIGGER_FILE}")

            except Exception as e:
                print(f"Error handling trigger: {e}")
                # Ensure the trigger file is removed even on error
                if os.path.exists(TRIGGER_FILE):
                     os.remove(TRIGGER_FILE)

        # 4. Handle text disappearing (clear playback)
        elif not current_normalized_text and last_read_normalized_text:
            # Subtitle disappeared, clear playback and last text
            cancel_playback()
            last_read_normalized_text = ""
            text_box.delete("1.0", tk.END)

        # 5. Handle simple GUI update if text changed but no trigger (Keeps GUI fresh)
        # We only update the GUI text box if the text changed but there was NO active trigger
        elif current_normalized_text and current_normalized_text != last_read_normalized_text and not trigger_exists:
             text_box.delete("1.0", tk.END)
             # --- FIX 3D: Insert the PROCESSED text ---
             text_box.insert("1.0", current_processed_text)


    except Exception as e:
        print(f"Error reading communication file: {e}")

    # Schedule the next check using the current interval from app_settings
    root.after(app_settings["file_watch_interval"], file_watcher)


# --- GUI and Settings Management ---


# Callback function used by OptionsWindow to save settings

def save_settings_callback(new_settings):
    """
    Updates the global app_settings dictionary, rebinds hotkeys, and saves to file.
    Called when the Options window is closed via 'Save'.
    """
    global app_settings

    # 1. Update the hotkey bindings (remove old, add new)
    old_speak_key = app_settings["speak_hotkey"]
    old_cancel_key = app_settings["cancel_hotkey"]

    try:
        # Unhook old bindings
        keyboard.remove_hotkey(old_speak_key)
        keyboard.remove_hotkey(old_cancel_key)
    except:
        # Fails silently if the hotkey was never bound or already removed
        pass

    # 2. Update the global dictionary
    app_settings.update(new_settings)

    # 3. Rebind new hotkeys
    keyboard.add_hotkey(app_settings["speak_hotkey"], global_on_speak_key)
    keyboard.add_hotkey(app_settings["cancel_hotkey"], cancel_playback)

    # 4. Update Renpy Checkbox in Main GUI (if it exists)
    renpy_mode_var.set(app_settings["renpy_mode"])

    # 5. Save the configuration to disk
    save_config(app_settings)

    # 6. Log the changes
    print(f"Hotkeys updated. Speak: '{app_settings['speak_hotkey']}', Cancel: '{app_settings['cancel_hotkey']}'")
    print(f"Polling Interval updated to: {app_settings['file_watch_interval']} ms")
    print(f"Renpy Mode set to: {app_settings['renpy_mode']}")


# Function to open the Options GUI
def open_options():
    """Opens the modal OptionsWindow, passing current settings and the save callback."""
    print("Options button pressed. Opening options window.")
    # Pass the current settings and the callback function
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

# Text box
text_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=80, height=15,
                                     font=("Arial", 12), bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white")
text_box.pack(padx=10, pady=10)

# --- Dropdowns side by side with labels ---
dropdowns_frame = tk.Frame(root, bg=BG_COLOR)
dropdowns_frame.pack(pady=10)

# Model frame
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

# Voice frame
voice_frame = tk.Frame(dropdowns_frame, bg=BG_COLOR)
voice_frame.grid(row=0, column=1, padx=10)
tk.Label(voice_frame, text="Select Voice:", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 10)).pack()
voice_var = tk.StringVar(value=DEFAULT_VOICE)
voice_dropdown = ttk.Combobox(voice_frame, textvariable=voice_var,
                              values=[DEFAULT_VOICE], state="readonly", font=("Arial", 10))
voice_dropdown.pack()

# Language frame
lang_frame = tk.Frame(dropdowns_frame, bg=BG_COLOR)
lang_frame.grid(row=0, column=2, padx=10)
tk.Label(lang_frame, text="Select Language:", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 10)).pack()
lang_var = tk.StringVar(value="default")
lang_dropdown = ttk.Combobox(lang_frame, textvariable=lang_var,
                             values=["default"], state="readonly", font=("Arial", 10))
lang_dropdown.pack()

# Update voices/languages
def update_model(event=None):
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

# --- Action Buttons Frame (Horizontal layout for Options, Speak, Pause, Cancel) ---
action_buttons_frame = tk.Frame(root, bg=BG_COLOR)
action_buttons_frame.pack(pady=5)

# Options Button (Positioned Left)
options_button = tk.Button(action_buttons_frame, text="Options", command=open_options,
                         font=("Arial", 12), bg=BTN_OPTIONS, fg="white", relief="flat", width=10)
options_button.pack(side=tk.LEFT, padx=5)

# Speak button uses text from its own textbox for manual testing (Positioned Second)
# NOTE: The command for this button must also be updated to ensure the displayed text is spoken.
speak_button = tk.Button(action_buttons_frame, text="Speak", command=lambda: speak_text_streaming(preprocess_text(text_box.get("1.0", tk.END).strip())),
                         font=("Arial", 12), bg=BTN_GREEN, fg="white", relief="flat", width=10)
speak_button.pack(side=tk.LEFT, padx=5)

pause_button = tk.Button(action_buttons_frame, text="Pause", command=pause_resume,
                         font=("Arial", 12), bg=BTN_ORANGE, fg="white", relief="flat", width=10)
pause_button.pack(side=tk.LEFT, padx=5)

cancel_button = tk.Button(action_buttons_frame, text="Cancel", command=cancel_playback,
                          font=("Arial", 12), bg=BTN_RED, fg="white", relief="flat", width=10)
cancel_button.pack(side=tk.LEFT, padx=5)


# --- Utility Buttons Frame (Scan, Clear, Paste) ---
utility_buttons_frame = tk.Frame(root, bg=BG_COLOR)
utility_buttons_frame.pack(pady=10)

def clear_text():
    text_box.delete("1.0", tk.END)

def paste_text():
    try:
        clipboard_content = root.clipboard_get()
        # --- Update paste_text to insert PROCESSED text ---
        processed_text = preprocess_text(clipboard_content)
        text_box.delete("1.0", tk.END)
        text_box.insert("1.0", processed_text)
        # --- End Update ---
    except tk.TclError:
        pass

# Scan Button - Positioned first in the utility frame
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

# BooleanVar is initialized with the current app_settings value
renpy_mode_var = tk.BooleanVar(value=app_settings["renpy_mode"])
renpy_mode_check = tk.Checkbutton(renpy_frame, text="Renpy Mode", variable=renpy_mode_var,
                                  bg=BG_COLOR, fg=FG_COLOR, selectcolor=ENTRY_BG,
                                  font=("Arial", 10), relief="flat",
                                  command=toggle_renpy_mode)
renpy_mode_check.pack(side=tk.LEFT, padx=10)
# ----------------------------------


# Initialize
update_model()

# --- Hotkey Functions ---
def global_on_speak_key():
    """Hotkey: Copy selected text, paste into textbox, and speak."""
    try:
        cancel_playback()
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.1)

        clipboard_content = root.clipboard_get()

        # --- FIX 2A: Preprocess the text ---
        processed_text = preprocess_text(clipboard_content)

        text_box.delete("1.0", tk.END)
        # --- FIX 2B: Insert the PROCESSED text ---
        text_box.insert("1.0", processed_text)

        # --- FIX 2C: Speak the PROCESSED text ---
        speak_text_streaming(processed_text)

    except Exception as e:
        print("Error copying selected text:", e)

# Initial Hotkey Bindings (Use settings loaded from config.json)
keyboard.add_hotkey(app_settings["speak_hotkey"], global_on_speak_key)
keyboard.add_hotkey(app_settings["cancel_hotkey"], cancel_playback)

# Start the file watching loop
root.after(app_settings["file_watch_interval"], file_watcher)

root.mainloop()
