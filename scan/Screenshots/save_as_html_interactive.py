import time
import os
import webbrowser
import sys
import pyautogui
import subprocess
import shutil

# Configuration
LINKS_FILE = "links.txt"
OUTPUT_DIR = os.path.abspath("html_output")
PAGE_LOAD_WAIT = 5 # Time for Cloudflare/JS to load
DOWNLOAD_WAIT = 2 # Time for download to finish before closing
PAUSE_BETWEEN_LINKS = 1

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

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"Error: {LINKS_FILE} not found.")
        return
        
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    try:
        with open(LINKS_FILE, "r") as f:
            links = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading links: {e}")
        return
    
    remaining_links = links.copy()

    print(f"Found {len(links)} links. Starting HTML extraction via browser automation...")
    print("1. Open your browser and ensure it's focused.")
    print("2. Make sure file downloads go to a predictable place or ask every time.")
    print("3. *** DO NOT USE YOUR COMPUTER WHILE THIS RUNS ***")
    print("   (Mouse/Keyboard movements will interfere)")
    print("Press Ctrl+C in this terminal to stop.")
    
    print("\nStarting in 5 seconds...")
    time.sleep(5)

    for i, link in enumerate(links):
        print(f"[{i+1}/{len(links)}] Processing: {link}")

        with pyautogui.hold('ctrl'):
            pyautogui.press(['t'])
        
        pyautogui.typewrite(link)
        time.sleep(PAUSE_BETWEEN_LINKS)
        pyautogui.press('enter')
        
        # 2. Wait for page load (adjust if connection slow)
        time.sleep(PAGE_LOAD_WAIT)
        
        # 3. Open Save As dialog (Ctrl+S)
        print("  Saving page...")

        pyautogui.hotkey('ctrl', 'shift', 'l')
        
        time.sleep(DOWNLOAD_WAIT)
        
        # 7. Close tab (Ctrl+W)
        print("  Closing tab...")
        pyautogui.hotkey('ctrl', 'w')

        # Remove processed link from links.txt so resume is easier on reruns.
        if remaining_links:
            remaining_links.pop(0)
            try:
                with open(LINKS_FILE, "w") as f:
                    if remaining_links:
                        f.write("\n".join(remaining_links) + "\n")
                    else:
                        f.write("")
            except Exception as e:
                print(f"  Warning: could not update {LINKS_FILE}: {e}")
        
        # Pause
        time.sleep(PAUSE_BETWEEN_LINKS)

    print("\nDone!")


webbrowser.open("https://www.cyberbackgroundchecks.com")

if __name__ == "__main__":
    main()

