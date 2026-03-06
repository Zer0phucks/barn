import subprocess
import os
import time
import sys

# Configuration
LINKS_FILE = "links.txt"
OUTPUT_DIR = "pdf_output"
CHROME_CMD = "google-chrome" # Or "chromium-browser" if needed

def main():
    if not os.path.exists(LINKS_FILE):
        print(f"Error: {LINKS_FILE} not found.")
        return

    # Create output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating output directory: {OUTPUT_DIR}")
        os.makedirs(OUTPUT_DIR)

    try:
        with open(LINKS_FILE, "r") as f:
            links = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading links: {e}")
        return

    print(f"Found {len(links)} links. Starting PDF generation...")
    print("Press Ctrl+C to stop at any time.")

    for i, link in enumerate(links):
        # Create a filename based on the URL or index
        # Using index is safer to avoid invalid filesystem characters
        filename = os.path.join(OUTPUT_DIR, f"page_{i+1:04d}.pdf")
        
        print(f"[{i+1}/{len(links)}] Saving: {link}")
        
        cmd = [
            CHROME_CMD,
            "--headless",
            "--disable-gpu",
            "--no-sandbox", # Often needed in container/script environments
            "--run-all-compositor-stages-before-draw", # Helps ensure page is fully rendered
            f"--print-to-pdf={filename}",
            link
        ]
        
        try:
            # Run the command with a timeout to prevent hanging
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            
            if result.returncode == 0:
                print(f"  -> Saved to {filename}")
            else:
                print(f"  -> Error (code {result.returncode}): {result.stderr.strip()}")
                
        except subprocess.TimeoutExpired:
            print(f"  -> Timeout processing {link}")
        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Exiting.")
            sys.exit(0)
        except Exception as e:
            print(f"  -> Unexpected error: {e}")

        # Optional: verify file exists and size
        if os.path.exists(filename) and os.path.getsize(filename) == 0:
            print("  -> Warning: PDF file is empty.")

    print("\nDone processing all links.")

if __name__ == "__main__":
    main()
