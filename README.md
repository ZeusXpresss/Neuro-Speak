<p align="center">
    <img src="ns-logo.png" alt="Neuro Speak Logo" width="150">
</p>


---

## Neuro Speak Overview

Your own custom uncensored private local text-to-speech program is here! Copy and paste text from a game or book and have TTS read it aloud. Alternatively, it can scan a region on your computer and read text (ie. Renpy games). Download any TTS model from hugging face or use default ones to get started!

---

## 💡 Install Instructions

```bash
git clone https://github.com/ZeusXpresss/Neuro-Speak.git

```

There is a install_dependencies.bat file inside the main folder you will need to run.  This will install all the dependencies and requirements that is needed for the program to work and it will check if you have the below installed to ensure the program works correctly.

You need Python 3.10 exactly, its the only stable version that I know works currently: https://www.python.org/downloads/release/python-3100/
You need to install NG-Speak, this is required for the TTS to actually speak: https://github.com/espeak-ng/espeak-ng/releases/tag/1.52.0
You need to install Visual Studio C++ Build Tools: https://visualstudio.microsoft.com/downloads/?q=build+tools

Lastly, You need to install Tesseract OCR manually: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
Default path expected by program: C:\Program Files\Tesseract-OCR\tesseract.exe

(You shouldn't get errors, but if you do, you can ask a LLM (like google gemini or ChatGPT) and upload the .bat and log file, they should walk you through the process)

## 💻 How to use

Open TTS_AI.py with the CMD console | There is a Run TTS.bat file.  You can edit this so its easier to open.
```bash
python "Path to TTS.AI.py"
pause
```
Once opened, the program will import all necessary dependencies.  After a bunch of debug information, the GUI should open. You need to select a Model and a Voice.  The model VITS and Voice p243 should be selected by default. (this is the best model/voice in my opinion)

You can type text into the text box and press the speak button.  You can also select any text you want (like something on a browser) and press z, pressing z will auto copy selected text and TTS will read it.

> [!TIP]
> You can change hotkeys in the options menu.  The hotkeys for scan mode are under development.  They work, you just cant change the hotkeys for scan mode just yet.

  Alternatively, if you are playing a game or reading a book that does not have copyable text, you can click the Scan button.  Hit select screen area, drag a selection on your primary monitor.  [If your game is on another monitor, you will need to change that monitor to be primary using the windows display settings]  After dragging a selection, press "Trigger Scan".  This will scan your region for WHITE text, then sends it to TTS to read.

If something does not work in the scan page, press the capture screenshot button.  This will create a png file in the TTS directory, this image shows you what the scanner saw.  Keep in mind that the Scanner only sees white text (ie. #ffffff).

If you are using this program for Renpy games.  Be sure to check the "Renpy Mode" in the TTS GUI, this essentially pre-processes text so the TTS speech is cleaner.  Example: It clears out line breaks so the TTS does not pause when a line break happens.  Instead it merges to 2 lines and creates a space, so the 2 lines are one sentence allowing TTS to say the line with no pauses.

## 🚀 Future In Developemnet Features

I plan to add a simple way to add an AI model.  Right now, the only way is my downloading your own and editing the code.

