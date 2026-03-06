import os
import shutil
import subprocess
import time
import webbrowser

import pyautogui


def open_target(url: str) -> None:
    firefox_path = shutil.which("firefox")

    # Try PATH first, then common Windows install locations.
    if firefox_path:
        subprocess.Popen([firefox_path, url])
        return

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
    ]

    for path in candidates:
        if os.path.exists(path):
            subprocess.Popen([path, url])
            return

    # Final fallback: open in system default browser.
    webbrowser.open(url)


url = "https://www.cyberbackgroundchecks.com/address/1609-BONITA-AVE/BERKELEY/94709"
open_target(url)
time.sleep(2)

# Kept from your original flow in case the page needs a manual Enter.
pyautogui.press("enter")
