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
import json # NEW: Import JSON library for file persistence

from options import OptionsWindow
from window_scanner import select_window_area

from TTS.api import TTS

# --- Configuration Constants (MOVED from TTS_AI.py) ---
CONFIG_FILE = "config.json"

DEFAULT_SETTINGS = {
    "speak_hotkey": "z",
    "cancel_hotkey": "x",
    "file_watch_interval": 200,
    "renpy_mode": True
}

app_settings = DEFAULT_SETTINGS.copy()

def load_config():
    """Loads settings from config.json or returns default settings if the file doesn't exist."""
    global app_settings
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_settings = json.load(f)
                # Merge loaded settings with defaults to handle new keys gracefully
                app_settings = {**DEFAULT_SETTINGS, **loaded_settings}
                print(f"Loaded settings from {CONFIG_FILE}.")
                return
        except json.JSONDecodeError:
            print(f"Error reading {CONFIG_FILE}. Using default settings.")

    app_settings = DEFAULT_SETTINGS.copy()
    print("No config file found or error occurred. Using default settings.")


def save_config(settings):
    """Saves the current application settings to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"Settings saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config file: {e}")


# Function to run when the Renpy Mode checkbox is toggled
def toggle_renpy_mode():
    """Updates global app_settings and prints a message for Renpy Mode state."""
    # This reflects the change in the main window's checkbox immediately to app_settings
    app_settings["renpy_mode"] = renpy_mode_var.get()
    print(f"Renpy Mode set to: {app_settings['renpy_mode']}")
    save_config(app_settings) # Auto-save when toggling this specific setting

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
