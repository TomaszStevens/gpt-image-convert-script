#!/usr/bin/env python3
"""
keyboard_automation.py

ZERO browser logic. All it does is send keystrokes:
- Cmd+T
- Paste URL
- Open DevTools
- Paste JS to open input
- Press Enter
- Press Down X times
- Press Enter
- Paste JS again
- Press Enter
- Press Down once
- Press Enter
- Paste prompt JS
- Press Enter
- Paste submit JS
- Press Enter
- Repeat for each run

All keystrokes are done using AppleScript (osascript).
Clipboard is set using pyperclip.
"""

import subprocess
import time
import random
import pyperclip
import os

# ---------------- CONFIG ----------------

URL = "https://chatgpt.com/g/g-p-6910e3729340819184bfbac0f7f6479f-images/project"     # the URL you want pasted after Cmd+T

# Folder containing files you want to iterate through.
# Run number = index in folder (1-based)
FILES_FOLDER = "/Users/tzx/desktop/gpt_automation/images"

# ----------------------- CONFIG -----------------------

# Your JS/text snippets (EXACTLY as you gave them)

OPEN_INPUT_JS = r"""document.querySelector('input[type="file"]')?.click();"""

PROMPT_JS_TEMPLATE = r"""
(() => {
  const selector = "#prompt-textarea > p";
  const text = `{PROMPT_TEXT}`; // use backticks to avoid escaping

  const el = document.querySelector(selector);
  if (!el) {
    console.error("❌ Element not found:", selector);
    return;
  }

  // Focus the element
  el.focus && el.focus();

  // If it's contenteditable, write into it and set caret at end
  if (el.isContentEditable) {
    // Replace content (keeps HTML-free plain text)
    el.innerText = text;

    // place caret at end
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);

    // Fire events so listeners react
    el.dispatchEvent(new InputEvent('input', { bubbles: true, cancelable: true, data: text }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    console.log("✅ Inserted text into contentEditable element.");
    return;
  }

  // Otherwise it's a normal <p> — set textContent and dispatch events
  el.textContent = text;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  el.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  console.log("✅ Inserted text into <p> element.");
})();
"""

CLICK_BUTTON_JS = r"""document.querySelector('#composer-submit-button').click()"""

# Timing
MIN_DELAY = 0.12
MAX_DELAY = 0.45
# ----------------------------------------


# ------------- AppleScript helpers -------------

def osa(cmd):
    """Run an AppleScript command."""
    subprocess.run(["osascript", "-e", cmd])


def sleep():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


def paste_clipboard():
    """Cmd+V"""
    osa('tell application "System Events" to keystroke "v" using {command down}')
    sleep()


def press_enter():
    """Key code 36 = Enter"""
    osa('tell application "System Events" to key code 36')
    sleep()


def press_down(short = False):
    """Key code 125 = Down arrow"""
    osa('tell application "System Events" to key code 125')
    time.sleep(0.07 if short else 0.5)


def cmd_t():
    osa('tell application "System Events" to keystroke "t" using {command down}')
    sleep()


def open_devtools():
    """Cmd+Option+J"""
    osa('tell application "System Events" to keystroke "j" using {command down, option down}')
    sleep()


# -------------- Main automation logic -----------------

def main():
    files = sorted([
        f for f in os.listdir(FILES_FOLDER)
        if os.path.isfile(os.path.join(FILES_FOLDER, f))
    ])

    print(f"[i] Found {len(files)-2} files.")
    print("[i] Starting in 5 seconds...")
    time.sleep(5)

    for index, filename in enumerate(files[2:len(files)], start=1):
        print(f"\n[i] Run {index}: {filename}")

        # 1. Cmd+T
        cmd_t()

        # 2. Paste URL
        pyperclip.copy(URL)
        paste_clipboard()
        press_enter()

        sleep()
        sleep()

        # 3. Open DevTools
        open_devtools()

        sleep()
        sleep()
        sleep()

        # 4. Paste OPEN_INPUT_JS
        pyperclip.copy(OPEN_INPUT_JS)
        paste_clipboard()
        sleep()
        sleep()
        press_enter()

        # 5. Wait for file dialog to open
        time.sleep(0.8)

        # 6. Press Down X times
        for _ in range(index+1):
            press_down(True)

        # 7. Press Enter to select
        press_enter()
        sleep()
        sleep()
        sleep()

        # 8. Paste OPEN_INPUT_JS again (for second image)
        # open_devtools()
        pyperclip.copy(OPEN_INPUT_JS)
        paste_clipboard()
        sleep()
        sleep()
        press_enter()

        time.sleep(0.7)

        # 9. Press Down ONCE for static image
        press_down()
        press_enter()
        sleep()
        sleep()
        sleep()

        # 10. Paste prompt JS
        prompt_text = f"Apply the artistic style, color palette, and texture of the second image to the first image while keeping its structure. Don't be afraid to vary colours and keep the colours more realistically similar to the first image. This image must be square."
        js = PROMPT_JS_TEMPLATE.replace("{PROMPT_TEXT}", prompt_text.replace("`", "\\`"))
        # open_devtools()
        pyperclip.copy(js)
        paste_clipboard()
        sleep()
        sleep()
        sleep()
        sleep()
        press_enter()

        # 11. Paste button click JS
        # open_devtools()
        sleep()
        sleep()
        sleep()
        pyperclip.copy(CLICK_BUTTON_JS)
        paste_clipboard()
        sleep()
        sleep()
        sleep()
        press_enter()

        # 12. Small wait before next iteration
        time.sleep(random.uniform(8.6,10 + random.gauss(6,1)))

    print("\n[i] ALL DONE.")


if __name__ == "__main__":
    main()
