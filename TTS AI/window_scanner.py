# window_scanner.py

import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
from PIL import Image
import pytesseract
import threading
from pynput import keyboard
from pynput import mouse
import time
import numpy as np
import cv2
import os
import pyautogui
import keyboard # Import for global hotkey

# --- Global Configuration and Styling ---
COMM_FILE = "tts_input.txt"
TRIGGER_FILE = "tts_trigger.txt" # Must match TTS AI.py
CANCEL_FILE = "tts_cancel.txt"   # ADDED: Must match TTS AI.py

# NEW: Continuous Scan Configuration
MAX_SCAN_TIME = 5.0 # seconds
SCAN_INTERVAL = 0.25 # seconds between retries

# Dark theme colors (Defined globally for accessibility)
BG_COLOR = "#2e2e2e"
FG_COLOR = "#ffffff"
BTN_BLUE = "#007bff"
BTN_GREEN = "#2e8b57"
ENTRY_BG = "#1e1e1e"

# Default path for Windows installations (adjust if needed)
DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- Globals ---
roi_rect = None  # (x1, y1, x2, y2) - Absolute screen coordinates
tesseract_path = DEFAULT_TESSERACT_PATH

# --- Helper Functions ---

def save_debug_image(img, prefix="debug"):
    """Saves the processed image with millisecond precision for unique filenames."""
    millis = int(round(time.time() * 1000))
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_ocr_image_{timestamp_str}_{millis % 1000:03d}.png"

    try:
        img.save(filename)
        print(f"Saved debug image: {filename}")
    except Exception as e:
        print(f"Error saving image: {e}")

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

def grab_and_ocr(rect):
    """
    Grabs screenshot, preprocesses (white text isolation), runs OCR.
    """
    global tesseract_path

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    if not rect:
        return "", None

    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1

    if width <= 0 or height <= 0:
        return f"Capture Error: Invalid ROI dimensions (W:{width}, H:{height}). Please reselect a valid area (min 10x10).", None

    # 1. Capture the region
    try:
        img_pil = pyautogui.screenshot(region=(x1, y1, width, height))
    except Exception as e:
        return f"Capture Error (pyautogui): {e}", None

    img_cv = np.array(img_pil)
    img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)

    # 2. Preprocessing (Color Masking for White Text)
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 180], dtype=np.uint8)
    upper_white = np.array([179, 70, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_white, upper_white)

    processed_image = mask
    processed_img_pil = Image.fromarray(processed_image)

    # 3. Run OCR
    try:
        # Use PSM 6 (single text line) is often best for subtitles.
        text = pytesseract.image_to_string(processed_img_pil, config='--oem 3 --psm 6')
        return text.strip(), processed_img_pil
    except pytesseract.TesseractNotFoundError:
        return "Tesseract Error: Path incorrect or Tesseract missing!", processed_img_pil
    except Exception as e:
        return f"OCR Runtime Error: {e}", processed_img_pil

def update_monitor_display(text_widget, text):
    """Updates the text box in the ScannerApp GUI."""
    text_widget.delete("1.0", tk.END)
    text_widget.insert("1.0", text)


def _write_communication_files(text, processed_img, app_instance):
    """Shared logic for writing text to files and saving debug images."""
    current_normalized_text = normalize_text(text)

    # 1. Write recognized text or clear the file
    with open(COMM_FILE, 'w', encoding='utf-8') as f:
        f.write(text)

    # 2. Write the trigger file only if meaningful text was detected
    if current_normalized_text:
        with open(TRIGGER_FILE, 'w', encoding='utf-8') as f:
            f.write("SPEAK")

        if app_instance.save_images_var.get() and processed_img:
            app_instance.text_widget.master.after(0, lambda img=processed_img: save_debug_image(img, prefix="change"))
        return True
    else:
        # If no text, ensure any old trigger is cleared
        if os.path.exists(TRIGGER_FILE):
            os.remove(TRIGGER_FILE)
        return False


def perform_single_scan(text_widget, app_instance):
    """
    Performs a single capture, OCR, and updates the text box and communication file.
    Used for the 'R' key (Scan Only).
    """
    global roi_rect

    if not roi_rect:
        text_widget.master.after(0, lambda t="Scan Error: ROI not selected.": update_monitor_display(text_widget, t))
        return

    current_text, processed_img = grab_and_ocr(roi_rect)
    is_error = "Error" in current_text

    # Update the GUI text box
    text_widget.master.after(0, lambda t=current_text: update_monitor_display(text_widget, t))

    if is_error:
        print(f"OCR Error detected: {current_text}")
        if app_instance.save_images_var.get() and processed_img:
            text_widget.master.after(0, lambda img=processed_img: save_debug_image(img, prefix="error"))
        return # Stop on error

    # --- Write to files ---
    try:
        if _write_communication_files(current_text, processed_img, app_instance):
            print("Single scan: Text found, trigger sent.")
        else:
            print("Single scan: No text detected, files cleared.")
    except Exception as e:
        print(f"Error writing to communication file or trigger file: {e}")


def perform_continuous_scan(text_widget, app_instance):
    """
    Performs continuous capture and OCR until text is found or MAX_SCAN_TIME expires.
    Used for the Spacebar hotkey (Click & Scan).
    """
    global roi_rect
    start_time = time.time()
    scan_count = 0

    print(f"Continuous scan loop started. Max time: {MAX_SCAN_TIME}s.") # UNIQUE START MESSAGE

    if not roi_rect:
        text_widget.master.after(0, lambda t="Scan Error: ROI not selected.": update_monitor_display(text_widget, t))
        return

    # Loop for MAX_SCAN_TIME or until text is found
    while time.time() - start_time < MAX_SCAN_TIME:
        scan_count += 1
        # Print a retry message after the first attempt
        if scan_count > 1:
            print(f"[{scan_count}/{int(MAX_SCAN_TIME/SCAN_INTERVAL) + 1}] Retrying scan...")

        current_text, processed_img = grab_and_ocr(roi_rect)
        is_error = "Error" in current_text

        # 1. Update the GUI text box
        text_widget.master.after(0, lambda t=current_text: update_monitor_display(text_widget, t))

        # Check for errors
        if is_error:
            print(f"OCR Error detected: {current_text}")
            if app_instance.save_images_var.get() and processed_img:
                text_widget.master.after(0, lambda img=processed_img: save_debug_image(img, prefix="error"))
            return # EXIT the scan loop on fatal error

        # Check for found text
        try:
            if _write_communication_files(current_text, processed_img, app_instance):
                print(f"Continuous scan: Text detected on scan {scan_count}. Writing files and stopping.")
                return # EXIT the scan loop upon success
        except Exception as e:
            print(f"Error writing communication file or trigger file: {e}")
            return # EXIT on file error

        # 2. Text not found, wait and retry
        time.sleep(SCAN_INTERVAL)

    # If the loop finishes without finding text
    print(f"Continuous scan terminated: Maximum time ({MAX_SCAN_TIME}s) reached. No text found.")

    # Clear communication files upon timeout
    text_widget.master.after(0, lambda t="Scan Timeout: No text found within limits.": update_monitor_display(text_widget, t))
    try:
        with open(COMM_FILE, 'w', encoding='utf-8') as f:
            f.write("")
        if os.path.exists(TRIGGER_FILE):
            os.remove(TRIGGER_FILE)
    except Exception as e:
        print(f"Error clearing files after timeout: {e}")


# --- Scanner Application GUI (Control Panel) ---

class ScannerApp:
    def __init__(self, master):
        self.master = master
        master.title("Scanner Control Panel")
        master.configure(bg=BG_COLOR)

        tesseract_frame = tk.Frame(master, bg=BG_COLOR)
        tesseract_frame.pack(pady=(10, 5), padx=10, fill='x')

        tk.Label(tesseract_frame, text="Tesseract Executable Path:", fg=FG_COLOR, bg=BG_COLOR, font=("Arial", 10, "bold")).pack(anchor='w')

        self.tesseract_path_var = tk.StringVar(value=tesseract_path)
        self.tesseract_path_label = tk.Label(tesseract_frame, textvariable=self.tesseract_path_var, fg="#aaaaaa", bg=BG_COLOR, font=("Arial", 9), anchor='w', wraplength=300)
        self.tesseract_path_label.pack(fill='x', pady=2)

        tk.Button(tesseract_frame, text="Set Tesseract Path", command=self.set_tesseract_path,
                  bg="#444444", fg="white", font=("Arial", 10)).pack(anchor='w', pady=(0, 5))

        tk.Label(master, text="2. Select Area (ROI):", fg=FG_COLOR, bg=BG_COLOR, font=("Arial", 10, "bold")).pack(pady=(10, 5), padx=10, anchor='w')
        self.select_button = tk.Button(master, text="Select Screen Area", command=self.select_area,
                                       bg=BTN_BLUE, fg="white", font=("Arial", 12, "bold"), width=20)
        self.select_button.pack(pady=5)

        roi_status_frame = tk.Frame(master, bg=BG_COLOR)
        roi_status_frame.pack(pady=(0, 10))

        self.roi_status_var = tk.StringVar(value="ROI: Not Selected")
        self.roi_status_label = tk.Label(roi_status_frame, textvariable=self.roi_status_var, fg="#aaaaaa", bg=BG_COLOR, font=("Arial", 9))
        self.roi_status_label.pack(side=tk.LEFT, padx=(10, 5))

        self.adjust_btn = tk.Button(roi_status_frame, text="Adjust Manually", command=self.manual_adjust_roi,
                                    bg="#444444", fg="white", font=("Arial", 9), state=tk.DISABLED)
        self.adjust_btn.pack(side=tk.LEFT, padx=5)


        tk.Label(master, text="Recognized Subtitle Text:", fg=FG_COLOR, bg=BG_COLOR, font=("Arial", 10, "bold")).pack(pady=(10, 5), padx=10, anchor='w')
        self.text_widget = scrolledtext.ScrolledText(master, height=5, width=40, wrap=tk.WORD,
                                                 font=("Arial", 11), bg=ENTRY_BG, fg='#00ff00',
                                                 insertbackground='white')
        self.text_widget.pack(padx=10, pady=5)

        debug_frame = tk.Frame(master, bg=BG_COLOR)
        debug_frame.pack(pady=(5, 10), padx=10, fill='x')

        self.save_images_var = tk.BooleanVar(value=False)
        tk.Checkbutton(debug_frame, text="Save Debug Image on Text Change",
                       variable=self.save_images_var,
                       bg=BG_COLOR, fg=FG_COLOR, selectcolor=BG_COLOR, font=("Arial", 10), relief=tk.FLAT).pack(side=tk.LEFT, anchor='w', padx=(0, 10))

        tk.Button(debug_frame, text="Capture Screenshot", command=self.capture_screenshot,
                  bg="#444444", fg="white", font=("Arial", 9)).pack(side=tk.LEFT, anchor='w')

        tk.Label(master, text="3. Hotkey Triggers:", fg=FG_COLOR, bg=BG_COLOR, font=("Arial", 10, "bold")).pack(pady=(10, 5), padx=10, anchor='w')

        button_frame = tk.Frame(master, bg=BG_COLOR)
        button_frame.pack(pady=(0, 20))

        # This button uses the continuous scan
        self.trigger_btn = tk.Button(button_frame, text="Trigger Scan (Spacebar)",
                                   command=lambda: self._trigger_scan_action(simulate_click=True),
                                   bg=BTN_GREEN, fg='white', font=("Arial", 12, "bold"), width=20, state=tk.DISABLED)
        self.trigger_btn.pack(side=tk.LEFT, padx=5)

        tk.Label(button_frame, text="Scan Only (R)", fg=FG_COLOR, bg=BG_COLOR, font=("Arial", 10)).pack(side=tk.LEFT, padx=15)


        # Hotkey bindings: Spacebar clicks, R does not.
        keyboard.add_hotkey('space', self.trigger_scan_global_space, suppress=True)
        keyboard.add_hotkey('r', self.trigger_scan_global_r, suppress=True)

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_tesseract_path(self):
        global tesseract_path
        new_path = simpledialog.askstring("Tesseract Path",
                                          "Enter the full path to your Tesseract executable (e.g., C:\\Program Files\\Tesseract-OCR\\tesseract.exe):",
                                          initialvalue=tesseract_path)

        if new_path:
            if os.path.exists(new_path) and os.path.isfile(new_path):
                tesseract_path = new_path
                self.tesseract_path_var.set(tesseract_path)
                messagebox.showinfo("Success", "Tesseract path updated successfully!")
            else:
                messagebox.showerror("Error", f"Path not found: {new_path}. Please check the path and try again.")

    def select_area(self):
        global root_selector
        root_selector = tk.Toplevel(self.master)
        AreaSelector(root_selector, self.selection_callback, bbox=None)
        self.master.wait_window(root_selector)

    def selection_callback(self, rect):
        global roi_rect
        if rect:
            roi_rect = rect
            self.roi_status_var.set(f"ROI: {roi_rect[0]},{roi_rect[1]} to {roi_rect[2]},{roi_rect[3]} (Selected)")
            self.trigger_btn.config(state=tk.NORMAL)
            self.adjust_btn.config(state=tk.NORMAL)
        else:
            roi_rect = None
            self.roi_status_var.set("ROI: Not Selected")
            self.trigger_btn.config(state=tk.DISABLED)
            self.adjust_btn.config(state=tk.DISABLED)

    def manual_adjust_roi(self):
        global roi_rect
        if not roi_rect:
            messagebox.showwarning("Warning", "Please select an area first before manually adjusting.")
            return

        current_str = f"{roi_rect[0]},{roi_rect[1]},{roi_rect[2]},{roi_rect[3]}"

        new_coords_str = simpledialog.askstring("Manual ROI Adjustment",
                                                "Enter new coordinates (x1,y1,x2,y2).",
                                                initialvalue=current_str)

        if new_coords_str:
            try:
                coords = [int(c.strip()) for c in new_coords_str.split(',')]
                if len(coords) == 4:
                    roi_rect = tuple(coords)
                    self.roi_status_var.set(f"ROI: {roi_rect[0]},{roi_rect[1]} to {roi_rect[2]},{roi_rect[3]} (Manually Set)")
                    self.trigger_btn.config(state=tk.NORMAL)
                    messagebox.showinfo("Success", "ROI coordinates updated.")
                else:
                    raise ValueError("Incorrect number of coordinates.")
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid coordinate format. Please use four integers separated by commas (e.g., 100,200,500,600). Error: {e}")

    def capture_screenshot(self):
        global roi_rect
        if not roi_rect:
            messagebox.showwarning("Warning", "Please select the area (ROI) first.")
            return

        # Always use a single scan for this manual button
        current_text, processed_img = grab_and_ocr(roi_rect)
        update_monitor_display(self.text_widget, current_text)

        if processed_img:
            save_debug_image(processed_img, prefix="manual_capture")

        if "Error" in current_text:
            messagebox.showerror("Capture Error", current_text)
        else:
            messagebox.showinfo("Capture Success", f"Text captured and debug image saved as manual_capture_ocr_image_*.png")


    # Hotkey Handler for Spacebar: CLICKS AND SCANS (Continuous)
    def trigger_scan_global_space(self):
        """Called by the global Spacebar hotkey (with click)."""
        # Run on the main Tkinter thread for safe GUI updates/state checks
        self.master.after(0, lambda: self._trigger_scan_action(simulate_click=True))

    # Hotkey Handler for 'R' key: ONLY SCANS (Single)
    def trigger_scan_global_r(self):
        """Called by the global 'R' key hotkey (scan only)."""
        # Run on the main Tkinter thread for safe GUI updates/state checks
        self.master.after(0, lambda: self._trigger_scan_action(simulate_click=False))

    def _trigger_scan_action(self, simulate_click):
        """The core scanning logic, conditionally simulating a left click and choosing scan type."""
        if not os.path.exists(tesseract_path) or not os.path.isfile(tesseract_path):
            messagebox.showerror("Error", "Tesseract executable not found. Please set the correct path above.")
            return

        if roi_rect and self.trigger_btn['state'] == tk.NORMAL:

            # --- NEW: File-Based Cancel for Reliable Stop (Spacebar or Button) ---
            if simulate_click: # Only cancel if it's the click/scan action
                try:
                    # 1. Write the dedicated CANCEL file
                    with open(CANCEL_FILE, 'w', encoding='utf-8') as f:
                        f.write("CANCEL")
                    print(f"Wrote cancel file: {CANCEL_FILE}")

                    # 2. Use a small, quick delay (0.1s) to allow the TTS_AI file watcher to process
                    # the cancel file before the new scan text is written.
                    time.sleep(0.1)

                except Exception as e:
                    print(f"Error writing cancel file: {e}")
            # -----------------------------------------------------------------------


            # --- CONDITIONAL Left Click ---
            if simulate_click:
                try:
                    # Initialize mouse controller from pynput
                    mouse_controller = mouse.Controller()
                    # Simulate a left click at the current cursor position
                    mouse_controller.click(mouse.Button.left)
                    print("Simulated left mouse click.")
                except Exception as e:
                    print(f"Error simulating mouse click: {e}")
            # ------------------------------

            self.adjust_btn.config(state=tk.DISABLED)

            # --- Select Scan Type (UNAMBIGUOUS LOGIC) ---
            if simulate_click:
                 # Hotkey is SPACEBAR or GUI Button
                 scan_target = perform_continuous_scan
                 self.trigger_btn.config(state=tk.DISABLED, text="Scanning (Continuous)...")
                 print("DEBUG: Selected CONTINUOUS scan (Spacebar/Button).")
            else:
                 # Hotkey is 'R'
                 scan_target = perform_single_scan
                 self.trigger_btn.config(state=tk.DISABLED, text="Scanning (Single)...")
                 print("DEBUG: Selected SINGLE scan (R key).")

            # Start the scan thread with the selected target function
            scan_thread = threading.Thread(target=scan_target, args=(self.text_widget, self), daemon=True)
            scan_thread.start()

            self.master.after(100, lambda: self._check_scan_thread(scan_thread))

        elif not roi_rect:
            messagebox.showwarning("Warning", "Please select the area (ROI) first.")

    def _check_scan_thread(self, thread):
        """Checks if the scan thread is done and re-enables the button."""
        if thread.is_alive():
            self.master.after(100, lambda: self._check_scan_thread(thread))
        else:
            self.trigger_btn.config(state=tk.NORMAL, text="Click & Scan (Spacebar)")
            self.adjust_btn.config(state=tk.NORMAL)
            print("Scan thread terminated.")

    def on_closing(self):
        # Clean up the global hotkeys
        try:
            keyboard.remove_hotkey('space')
            keyboard.remove_hotkey('r')
        except KeyError:
            pass
        self.master.destroy()

# --- Transparent Selection GUI (Same as before) ---

class AreaSelector:
    def __init__(self, master, callback, bbox=None):
        self.master = master
        self.callback = callback

        master.title("Select Subtitle Area")
        master.attributes('-alpha', 0.3)
        master.overrideredirect(True)

        self.screen_width = master.winfo_screenwidth()
        self.screen_height = master.winfo_screenheight()
        master.geometry(f"{self.screen_width}x{self.screen_height}+0+0")

        master.update_idletasks()

        self.window_x = master.winfo_x()
        self.window_y = master.winfo_y()

        self.start_x_local = None
        self.start_y_local = None
        self.current_x_local = None
        self.current_y_local = None
        self.rect_id = None

        self.canvas = tk.Canvas(master, cursor="cross", bg='grey', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.instruction_frame = tk.Frame(master, bg='white', bd=2, relief=tk.RAISED)
        self.instruction_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        tk.Label(self.instruction_frame, text="Drag to select the subtitle area.\nRight-click to cancel.", font=("Arial", 16), bg='white', fg='black').pack(padx=20, pady=10)

        master.bind("<Button-3>", self.on_right_click)

    def on_button_press(self, event):
        self.start_x_local = event.x
        self.start_y_local = event.y
        self.current_x_local = event.x

        if self.rect_id:
            self.canvas.delete(self.rect_id)

        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline='red', width=3)

    def on_mouse_drag(self, event):
        self.current_x_local = event.x
        self.current_y_local = event.y

        self.canvas.coords(self.rect_id, self.start_x_local, self.start_y_local, self.current_x_local, self.current_y_local)

    def on_button_release(self, event):
        self.master.unbind("<ButtonPress-1>")
        self.master.unbind("<B1-Motion>")
        self.master.unbind("<ButtonRelease-1>")

        x1_local = min(self.start_x_local, self.current_x_local)
        y1_local = min(self.start_y_local, self.current_y_local)
        x2_local = max(self.start_x_local, self.current_x_local)
        y2_local = max(self.start_y_local, self.current_y_local)

        x1_abs = x1_local + self.window_x
        y1_abs = y1_local + self.window_y
        x2_abs = x2_local + self.window_x
        y2_abs = y2_local + self.window_y

        if abs(x2_abs - x1_abs) > 10 and abs(y2_abs - y1_abs) > 10:
            rect = (x1_abs, y1_abs, x2_abs, y2_abs)
            print(f"ROI selected: {rect}.")
            self.callback(rect)
            self.master.destroy()
        else:
            messagebox.showerror("Selection Error", "Area too small (min 10x10 pixels required). Please try again.")
            self.callback(None)
            self.master.destroy()

    def on_right_click(self, event):
        print("Selection cancelled.")
        self.callback(None)
        self.master.destroy()


# --- Main Execution (Same as before) ---

def launch_scanner_app():
    """Initial function to launch the main scanner control GUI."""
    root_scanner = tk.Tk()
    app = ScannerApp(root_scanner)
    root_scanner.mainloop()

select_window_area = launch_scanner_app

if __name__ == "__main__":
    print("Launched window selection GUI: window_scanner.py")
    launch_scanner_app()
