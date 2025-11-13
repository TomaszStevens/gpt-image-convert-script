#!/usr/bin/env python3
"""
keyboard_automation.py

Automates browser interactions via keystrokes and AppleScript.
Uploads files in batches (default size 3), runs prompt JS, then for each batch:
- Waits while randomly switching tabs 2..N (3–7s delay, visit-any-within-30s policy),
- Downloads results (starting at tab 2), verifying success via spacers,
- Marks failures with 'error_<filename>.txt' in the output folder,
- Closes the batch tabs (ensuring we go to tab 2 before closing).

Also creates 'spacer' marker files at start in ~/Downloads to track new downloads.
"""

import subprocess
import time
import random
import pyperclip
import os
import shutil
from itertools import islice
import sys

# ---------------- CONFIG ----------------

URL = '<url here'

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

FILES_FOLDER = os.path.join(PROJECT_ROOT, "images")
STYLE_FOLDER = os.path.join(PROJECT_ROOT, "style")
TEMP_UPLOAD_DIR = os.path.join(PROJECT_ROOT, "tmp_upload")
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "out")

ENABLE_DOWNLOADS = True
DOWNLOADS_FOLDER = os.path.expanduser("~/Downloads")

# Batch control
BATCH_SIZE = 3
BATCH_WAIT_SECONDS = 180  # how long we "idle" & rotate before starting downloads

# “Human” tab-rotation behavior
TAB_SWITCH_MIN_DELAY = 3
TAB_SWITCH_MAX_DELAY = 7
TAB_VISIT_MAX_AGE = 30

# Timing for micro-delays
MIN_DELAY = 0.12
MAX_DELAY = 0.45

# ---------------- JS SNIPPETS ----------------

OPEN_INPUT_JS = r"""document.querySelector('input[type="file"]')?.click();"""

PROMPT_JS_TEMPLATE = r"""
(() => {
  const selector = "#prompt-textarea > p";
  const text = `{PROMPT_TEXT}`;

  const el = document.querySelector(selector);
  if (!el) {
    console.error("❌ Element not found:", selector);
    return;
  }

  el.focus && el.focus();

  if (el.isContentEditable) {
    el.innerText = text;
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, data: text }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    console.log("✅ Inserted text into contentEditable element.");
    return;
  }

  el.textContent = text;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  console.log("✅ Inserted text into <p> element.");
})();
"""

CLICK_BUTTON_JS = r"""document.querySelector('#composer-submit-button').click()"""

# ---------------- APPLESCRIPT HELPERS ----------------

def osa(cmd):
    subprocess.run(["osascript", "-e", cmd])

def sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

def paste_clipboard():
    osa('tell application "System Events" to keystroke "v" using {command down}')
    sleep()

def press_enter():
    osa('tell application "System Events" to key code 36')
    sleep()

def press_down(short=False):
    osa('tell application "System Events" to key code 125')
    time.sleep(0.07 if short else 0.5)

def cmd_t():
    osa('tell application "System Events" to keystroke "t" using {command down}')
    sleep()

def open_devtools():
    osa('tell application "System Events" to keystroke "j" using {command down, option down}')
    sleep()

def cmd_digit(n: int):
    osa(f'tell application "System Events" to keystroke "{n}" using {{command down}}')
    sleep()

def cmd_w():
    osa('tell application "System Events" to keystroke "w" using {command down}')
    sleep()

# ---------------- FILESYSTEM HELPERS ----------------

def wipe_tmp_upload():
    if not os.path.exists(TEMP_UPLOAD_DIR):
        os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
        return

    for f in os.listdir(TEMP_UPLOAD_DIR):
        try:
            path = os.path.join(TEMP_UPLOAD_DIR, f)
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        except Exception as e:
            print(f"⚠️ Could not remove {f}: {e}")

    print(f"[i] Cleared tmp_upload folder: {TEMP_UPLOAD_DIR}")


def copy_initial_style():
    style_dir = os.path.dirname(STYLE_FOLDER)
    files = sorted([
        f for f in os.listdir(style_dir)
        if os.path.isfile(os.path.join(style_dir, f)) and not f.startswith(".")
    ])
    if not files:
        print("⚠️ No style files found.")
        return None

    first_file = files[0]
    src = os.path.join(style_dir, first_file)
    ext = os.path.splitext(first_file)[1]
    dest = os.path.join(TEMP_UPLOAD_DIR, "zzzzzz_style" + ext)

    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    shutil.copy2(src, dest)

    print(f"[i] Copied initial style file → {dest}")
    return dest


def create_download_spacers(count=20):
    """Create 'spacer' empty files to mark the Downloads folder before downloads."""
    os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)
    for i in range(count):
        path = os.path.join(DOWNLOADS_FOLDER, f"spacer_{i+1:04d}.tmp")
        with open(path, "w"):
            pass
    print(f"[i] Created {count} spacer files in {DOWNLOADS_FOLDER}")

def cleanup_download_spacers():
    """Remove all spacer_XXXX.tmp files."""
    removed = 0
    for f in os.listdir(DOWNLOADS_FOLDER):
        if f.startswith("spacer_") and f.endswith(".tmp"):
            try:
                os.remove(os.path.join(DOWNLOADS_FOLDER, f))
                removed += 1
            except Exception as e:
                print(f"⚠️ Could not remove {f}: {e}")
    print(f"[i] Cleaned up {removed} spacer files from {DOWNLOADS_FOLDER}")

def get_latest_spacer_time():
    """Return the newest spacer file modification time."""
    spacers = [
        os.path.join(DOWNLOADS_FOLDER, f)
        for f in os.listdir(DOWNLOADS_FOLDER)
        if f.startswith("spacer_") and f.endswith(".tmp")
    ]
    if not spacers:
        return 0
    return max(os.path.getmtime(f) for f in spacers)

def download_is_success(timestamp):
    """Count how many files in Downloads are newer than the given timestamp."""
    files = [
        os.path.join(DOWNLOADS_FOLDER, f)
        for f in os.listdir(DOWNLOADS_FOLDER)
        if os.path.isfile(os.path.join(DOWNLOADS_FOLDER, f)) and not f.startswith(".")
    ]
    return sum(os.path.getmtime(f) > timestamp for f in files) > 0

def mark_download_error(filename):
    """Create an error_<filename>.txt file in OUTPUT_FOLDER."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    name = os.path.splitext(filename)[0]
    error_path = os.path.join(OUTPUT_FOLDER, f"error_{name}.txt")
    with open(error_path, "w") as f:
        f.write("An error occurred for this file during download.\n")
    print(f"❌ Download failed: {filename} — wrote {error_path}")

def move_latest_download(target_name):
    """Move the most recent file from ~/Downloads to OUTPUT_FOLDER."""
    files = [
        os.path.join(DOWNLOADS_FOLDER, f)
        for f in os.listdir(DOWNLOADS_FOLDER)
        if os.path.isfile(os.path.join(DOWNLOADS_FOLDER, f)) and not f.startswith(".")
    ]
    if not files:
        print("⚠️ No downloads found.")
        return
    latest = max(files, key=os.path.getctime)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    ext = os.path.splitext(latest)[1]
    dest = os.path.join(OUTPUT_FOLDER, target_name + ext)
    try:
        os.rename(latest, dest)
        print(f"✅ Saved {dest}")
    except Exception as e:
        print(f"⚠️ Could not move download: {e}")

# ---------------- MISC HELPERS ----------------

def open_chrome():
    osa('tell application "Google Chrome" to activate')

def add_base_image(path):
    shutil.copy2(path, TEMP_UPLOAD_DIR)
    print(f"[i] Added {os.path.basename(path)} to temp folder.")

def cleanup_base_image(path):
    target = os.path.join(TEMP_UPLOAD_DIR, os.path.basename(path))
    if os.path.exists(target):
        os.remove(target)
        print(f"[i] Removed {os.path.basename(path)} from temp folder.")

def chunked(iterable, size):
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            return
        yield chunk

def rotate_tabs_humanly(tabs):
    if not tabs:
        return
    current = tabs[0]
    cmd_digit(current)
    last_visit = {t: 0 for t in tabs}
    last_visit[current] = time.time()

    end_time = time.time() + BATCH_WAIT_SECONDS
    while time.time() < end_time:
        if len(tabs) > 1:
            now = time.time()
            candidates = [t for t in tabs if t != current]
            overdue = [t for t in candidates if (now - last_visit.get(t, 0)) >= TAB_VISIT_MAX_AGE]

            if overdue:
                nxt = random.choice(overdue)
            else:
                nxt = random.choice(candidates)

            cmd_digit(nxt)
            last_visit[nxt] = time.time()
            current = nxt

            time.sleep(random.uniform(TAB_SWITCH_MIN_DELAY, TAB_SWITCH_MAX_DELAY))
        else:
            time.sleep(BATCH_WAIT_SECONDS + 2)

# ---------------- CORE AUTOMATION ----------------

def upload_one_file(base_image_path):
    add_base_image(base_image_path)
    cmd_t()
    pyperclip.copy(URL)
    paste_clipboard()
    press_enter()
    sleep(); sleep()
    open_devtools()
    sleep(); sleep(); sleep()

    pyperclip.copy(OPEN_INPUT_JS)
    paste_clipboard(); sleep(); sleep(); press_enter()
    time.sleep(0.8)
    press_down(True); press_enter()
    sleep(); sleep(); sleep()

    pyperclip.copy(OPEN_INPUT_JS)
    paste_clipboard(); sleep(); sleep(); press_enter()
    time.sleep(0.7)
    press_down(); time.sleep(0.7); press_down(); time.sleep(0.3); press_enter()
    sleep(); sleep(); sleep()

    prompt_text = (
        "Apply the artistic style, color palette, and texture of the second image "
        "to the first image while keeping its structure. "
        "Don't be afraid to vary colours and keep the colours more realistically "
        "similar to the first image. This image must be square."
    )
    js = PROMPT_JS_TEMPLATE.replace("{PROMPT_TEXT}", prompt_text.replace("`", "\\`"))
    pyperclip.copy(js)
    paste_clipboard(); sleep(); sleep(); sleep(); sleep(); press_enter()
    sleep(); sleep(); sleep()
    pyperclip.copy(CLICK_BUTTON_JS)
    paste_clipboard(); sleep(); sleep(); sleep(); press_enter()
    cleanup_base_image(base_image_path)
    time.sleep(random.uniform(8.6, 10 + random.gauss(6, 1)))

def download_for_batch(batch_files):
    if not ENABLE_DOWNLOADS:
        return
    cmd_digit(2)
    latest_spacer_time = get_latest_spacer_time()
    failed_count = 0
    completed_downloads = 0

    for i, filename in enumerate(batch_files):
        base_name, _ = os.path.splitext(filename)
        print(f"[i] Downloading result for: {base_name}")
        cmd_digit(2 + i)
        pyperclip.copy('document.querySelector("span:nth-child(3) > button").click()')
        paste_clipboard(); press_enter()
        time.sleep(5 + random.uniform(1, 3))

        # Check new files count
        success = download_is_success(latest_spacer_time)
        if not success:
            mark_download_error(filename)
            failed_count += 1
        else:
            move_latest_download(base_name)
            completed_downloads += 1

        time.sleep(5)

def close_batch_tabs(batch_count):
    if batch_count <= 0:
        return
    cmd_digit(2)
    for _ in range(batch_count):
        cmd_w()
        time.sleep(random.uniform(0.2, 0.5))

# ---------------- MAIN ----------------

def main():
    create_download_spacers()
    copy_initial_style()
    wipe_tmp_upload()
    open_chrome()

    files = sorted([
        f for f in os.listdir(FILES_FOLDER)
        if os.path.isfile(os.path.join(FILES_FOLDER, f)) and not f.startswith(".")
    ])
    print(f"[i] Found {len(files)} files.")
    print("[i] Starting in 5 seconds...")
    time.sleep(5)

    for batch_index, batch in enumerate(chunked(files, BATCH_SIZE), start=1):
        print(f"\n========== BATCH {batch_index} ({len(batch)} file(s)) ==========")
        for index, filename in enumerate(batch, start=1):
            base_image_path = os.path.join(FILES_FOLDER, filename)
            print(f"\n[i] Batch {batch_index} — setup {index}/{len(batch)}: {filename}")
            upload_one_file(base_image_path)
        print("\n✅ All uploads for this batch queued.")
        if ENABLE_DOWNLOADS:
            print("\n[i] Entering wait period with randomized tab switching...")
            tabs = [2 + i for i in range(len(batch))]
            rotate_tabs_humanly(tabs)
            print("\n[i] Starting download cycle for this batch (from tab 2)...")
            download_for_batch(batch)
            print("\n[i] Closing batch tabs...")
            close_batch_tabs(len(batch))
        print(f"✅ Finished BATCH {batch_index}.\n")

    cleanup_download_spacers()
    print("✅ All batches complete. Done.")

if __name__ == "__main__":
    main()
