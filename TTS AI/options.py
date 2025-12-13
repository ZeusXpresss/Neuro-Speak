import tkinter as tk
from tkinter import ttk

# --- Configuration for consistent styling ---
BG_COLOR = "#1e1e1e"
FG_COLOR = "#ffffff"
ENTRY_BG = "#2d2d2d"
BTN_BLUE = "#007bff"
BTN_GREY = "#444444"
NAV_BG = "#2c2c2c" # Background for the navigation menu (tabs)
NAV_ACTIVE_BG = "#3e3e3e" # Background for the active selected tab
NAV_WIDTH = 15 # Width of the navigation column in character units

class OptionsWindow(tk.Toplevel):
    """
    A separate Toplevel window for application options and settings,
    featuring a tabbed navigation panel on the left.
    """
    def __init__(self, master, current_settings, save_callback):
        super().__init__(master)
        self.title("Application Options")
        self.configure(bg=BG_COLOR)
        self.transient(master) # Set to be on top of the parent window
        self.grab_set()        # Makes the window modal
        self.protocol("WM_DELETE_WINDOW", self.cancel) # Handle window close

        # Data storage and callback
        self.current_settings = current_settings

        # --- NEW: Ensure scanning hotkeys exist in settings with defaults ---
        if 'hotkey_continuous_scan' not in self.current_settings:
            self.current_settings['hotkey_continuous_scan'] = 'space'
        if 'hotkey_reset_crop' not in self.current_settings:
            self.current_settings['hotkey_reset_crop'] = 'ctrl+r'
        # -------------------------------------------------------------------

        self.save_callback = save_callback

        # Dictionary to hold content frames
        self.content_frames = {}
        # Variable to track the currently selected navigation button
        self.active_nav_var = tk.StringVar()

        self.create_widgets()

        # FIX: Temporarily pack the widest frame to force correct sizing
        # The 'Scanning' frame is the widest due to the long hotkey descriptions.
        self.content_frames["Scanning"].pack(fill="both", expand=True, padx=10, pady=10)

        # Calculate size and center
        self.center_window(master)

        # Show the desired default tab
        self.show_frame("Hotkeys")

    def center_window(self, master):
        """Centers the window relative to the master window, dynamically scaling to content."""
        if master:
            # Force Tkinter to calculate the required size based on the packed widgets
            self.update_idletasks()

            width = self.winfo_width()
            height = self.winfo_height()

            master_x = master.winfo_x()
            master_y = master.winfo_y()
            master_width = master.winfo_width()
            master_height = master.winfo_height()

            x = master_x + (master_width // 2) - (width // 2)
            y = master_y + (master_height // 2) - (height // 2)

            self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        # --- Main Layout Frames ---
        main_container = tk.Frame(self, bg=BG_COLOR)
        main_container.pack(fill="both", expand=True)

        # 1. Navigation Panel (Left Side)
        nav_frame = tk.Frame(main_container, width=NAV_WIDTH*10, bg=NAV_BG)
        nav_frame.pack(side="left", fill="y")
        nav_frame.pack_propagate(False)

        # 2. Content Area (Right Side)
        self.content_container = tk.Frame(main_container, bg=BG_COLOR, padx=10, pady=10)
        self.content_container.pack(side="right", fill="both", expand=True)

        # 3. Footer/Button Area (Bottom)
        footer_frame = tk.Frame(self, bg=NAV_BG, pady=10)
        footer_frame.pack(fill="x", side="bottom")

        # --- Populate Navigation Panel (no change) ---
        self.nav_buttons = {}
        nav_items = ["Hotkeys", "Scanning"]

        for item in nav_items:
            btn = tk.Radiobutton(nav_frame, text=item, variable=self.active_nav_var, value=item,
                                 indicatoron=0,
                                 width=NAV_WIDTH, anchor="w",
                                 font=("Arial", 11),
                                 bg=NAV_BG, fg=FG_COLOR,
                                 selectcolor=NAV_ACTIVE_BG,
                                 activebackground=NAV_ACTIVE_BG, activeforeground=FG_COLOR,
                                 bd=0, relief="flat",
                                 command=lambda name=item: self.show_frame(name))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[item] = btn

        # --- Populate Content Frames ---
        self.create_hotkey_frame()
        self.create_scanning_frame()

        # --- Footer Buttons (no change) ---
        button_frame = tk.Frame(footer_frame, bg=NAV_BG)
        button_frame.pack(side="right", padx=10)

        save_button = tk.Button(button_frame, text="Save Settings", command=self.save,
                                font=("Arial", 11), bg=BTN_BLUE, fg="white", relief="flat", padx=10)
        save_button.pack(side="left", padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=self.cancel,
                                  font=("Arial", 11), bg=BTN_GREY, fg="white", relief="flat", padx=10)
        cancel_button.pack(side="left", padx=5)

    def show_frame(self, frame_name):
        """Hides all content frames and displays the selected one."""
        frame = self.content_frames.get(frame_name)
        if frame:
            for f in self.content_frames.values():
                f.pack_forget()

            frame.pack(fill="both", expand=True, padx=10, pady=10)
            self.active_nav_var.set(frame_name)

    def create_hotkey_frame(self):
        """Creates the content panel for Hotkey settings (Global Z/X)."""
        frame = tk.Frame(self.content_container, bg=BG_COLOR)
        self.content_frames["Hotkeys"] = frame

        tk.Label(frame, text="Global Hotkeys Configuration", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(0, 20))

        # Hotkey Z (Speak/Copy)
        hkz_frame = tk.Frame(frame, bg=BG_COLOR)
        hkz_frame.pack(fill="x", pady=8)
        tk.Label(hkz_frame, text="Global Speak/Copy Hotkey:", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left")

        self.hkz_var = tk.StringVar(value=self.current_settings["speak_hotkey"])
        self.hkz_entry = tk.Entry(hkz_frame, textvariable=self.hkz_var, bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white", width=10)
        self.hkz_entry.pack(side="left", padx=5)
        tk.Label(hkz_frame, text="Triggers Ctrl+C, pastes the clipboard text, and starts TTS.", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

        # Hotkey X (Cancel)
        hkx_frame = tk.Frame(frame, bg=BG_COLOR)
        hkx_frame.pack(fill="x", pady=8)
        tk.Label(hkx_frame, text="Global Cancel Hotkey:", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left")

        self.hkx_var = tk.StringVar(value=self.current_settings["cancel_hotkey"])
        self.hkx_entry = tk.Entry(hkx_frame, textvariable=self.hkx_var, bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white", width=10)
        self.hkx_entry.pack(side="left", padx=5)
        tk.Label(hkx_frame, text="Immediately stops current speech playback.", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

    def create_scanning_frame(self):
        """Creates the content panel for Scanning settings, including configurable hotkeys."""
        frame = tk.Frame(self.content_container, bg=BG_COLOR)
        self.content_frames["Scanning"] = frame

        tk.Label(frame, text="Scanning Configuration", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(0, 20))

        # File Polling Interval
        polling_frame = tk.Frame(frame, bg=BG_COLOR)
        polling_frame.pack(fill="x", pady=8)
        tk.Label(polling_frame, text="File Polling Interval (ms):", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left")

        self.polling_var = tk.StringVar(value=str(self.current_settings["file_watch_interval"]))
        self.polling_entry = tk.Entry(polling_frame, textvariable=self.polling_var, bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white", width=10)
        self.polling_entry.pack(side="left", padx=5)
        tk.Label(polling_frame, text="Time between checks for new subtitle text.", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

        # Renpy Mode Toggle
        renpy_frame = tk.Frame(frame, bg=BG_COLOR)
        renpy_frame.pack(fill="x", pady=8)

        self.renpy_mode_var = tk.BooleanVar(value=self.current_settings["renpy_mode"])
        tk.Checkbutton(renpy_frame, text="Enable Renpy Mode Processing", variable=self.renpy_mode_var,
                       bg=BG_COLOR, fg=FG_COLOR, selectcolor=ENTRY_BG, activebackground=BG_COLOR, activeforeground=FG_COLOR,
                       font=("Arial", 11), relief="flat", bd=0).pack(side="left")
        tk.Label(renpy_frame, text="(Removes character names and cleans text for Renpy games.)", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

        # --- Region Selection Hotkeys Configuration (NEW INPUTS) ---
        tk.Label(frame, text="--- Region Selection Hotkeys (Active During Scan Mode) ---", font=("Arial", 12, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(20, 10))

        # Continuous Scan Hotkey
        hki_frame = tk.Frame(frame, bg=BG_COLOR)
        hki_frame.pack(fill="x", pady=8)
        tk.Label(hki_frame, text="Continuous Scan Toggle Key:", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left")

        self.hki_continuous_var = tk.StringVar(value=self.current_settings["hotkey_continuous_scan"])
        tk.Entry(hki_frame, textvariable=self.hki_continuous_var, bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white", width=10).pack(side="left", padx=5)
        tk.Label(hki_frame, text="Starts/Stops repeating the OCR scan on trigger file clear (e.g., 'space', 't').", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

        # Reset Crop Hotkey
        hkr_frame = tk.Frame(frame, bg=BG_COLOR)
        hkr_frame.pack(fill="x", pady=8)
        tk.Label(hkr_frame, text="Reset/Re-crop Key:", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left")

        self.hki_reset_var = tk.StringVar(value=self.current_settings["hotkey_reset_crop"])
        tk.Entry(hkr_frame, textvariable=self.hki_reset_var, bg=ENTRY_BG, fg=FG_COLOR, insertbackground="white", width=10).pack(side="left", padx=5)
        tk.Label(hkr_frame, text="Resets the selection area to allow re-drawing the ROI (e.g., 'r', 'q').", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", anchor="w")

        # Non-Configurable Mouse Bindings (Simplified Display)
        tk.Label(frame, text="\n--- Non-Configurable Mouse Bindings ---", font=("Arial", 12, "bold"), bg=BG_COLOR, fg=FG_COLOR).pack(anchor="w", pady=(10, 5))

        hotkey_desc = {
            "Right Mouse Button": "Cancel region selection and close the overlay.",
            "Left Mouse Drag": "Define or adjust the scanning area (ROI).",
        }

        for key, description in hotkey_desc.items():
            key_frame = tk.Frame(frame, bg=BG_COLOR)
            key_frame.pack(fill="x", pady=2)

            tk.Label(key_frame, text=f"{key}:", width=25, anchor="w", bg=BG_COLOR, fg=FG_COLOR, font=("Arial", 11, "bold")).pack(side="left")
            tk.Label(key_frame, text=description, anchor="w", bg=BG_COLOR, fg=FG_COLOR).pack(side="left", fill="x")

        # ----------------------------------------------------

    def save(self):
        """
        Gathers settings and calls the external save_callback to update the main app state.
        """
        try:
            new_settings = {
                "speak_hotkey": self.hkz_var.get().strip().lower(),
                "cancel_hotkey": self.hkx_var.get().strip().lower(),
                "file_watch_interval": int(self.polling_var.get()),
                "renpy_mode": self.renpy_mode_var.get(),
                # NEW SCANNING HOTKEYS
                "hotkey_continuous_scan": self.hki_continuous_var.get().strip().lower(),
                "hotkey_reset_crop": self.hki_reset_var.get().strip().lower(),
            }

            self.save_callback(new_settings)

            print("Settings saved and main app updated.")
            self.destroy()
            self.grab_release()

        except ValueError:
            print("Error: File Polling Interval must be an integer.")

    def cancel(self):
        """Closes the options window without saving."""
        print("Options cancelled.")
        self.destroy()
        self.grab_release()
