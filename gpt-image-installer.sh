#!/bin/sh

set -e
set -u

TARGET_DIR="$HOME/automation"
BIN_DIR="$HOME/bin"

echo "📦 Installing automation tools..."

# --- Create installation directory ---
if [ ! -d "$TARGET_DIR" ]; then
    echo "→ Creating directory: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
else
    echo "→ Directory already exists: $TARGET_DIR"
fi

cd "$TARGET_DIR"

# --- Pull the repo ---
GIT_URL="https://github.com/TomaszStevens/gpt-image-convert-script.git"

if [ -d "$TARGET_DIR/.git" ]; then
    echo "→ Repo already installed, pulling latest..."
    git pull --rebase
else
    echo "→ Cloning repo..."
    git clone "$GIT_URL" "$TARGET_DIR"
fi

# --- Prompt user for URL and write to src/url.txt ---
URL_FILE="$TARGET_DIR/src/url.txt"

echo ""
printf "🌐 Enter the URL to store in src/url.txt: "
read USER_URL

echo "→ Writing URL to $URL_FILE"
echo "$USER_URL" > "$URL_FILE"
echo "✓ URL saved."

# --- Create venv ---
echo "→ Creating Python virtual environment..."
python3 -m venv .venv

# shellcheck source=/dev/null
. "$TARGET_DIR/.venv/bin/activate"

# --- Install dependencies ---
if [ -f "requirements.txt" ]; then
    echo "→ Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "⚠️ No requirements.txt found — skipping dependency install."
fi


# --- Ensure ~/bin exists and is on PATH ---
if [ ! -d "$BIN_DIR" ]; then
    echo "→ Creating directory: $BIN_DIR"
    mkdir -p "$BIN_DIR"
fi

# Add to .zshrc if missing
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    echo "→ Adding ~/bin to PATH in ~/.zshrc"
    echo "\n# Add user bin directory\nexport PATH=\"\$HOME/bin:\$PATH\"" >> "$HOME/.zshrc"
fi


# --- Create launcher script ---
LAUNCH_SCRIPT="$BIN_DIR/gpt-converter"

echo "→ Creating launcher script at $LAUNCH_SCRIPT"

cat > "$LAUNCH_SCRIPT" <<EOF
#!/bin/sh
. "$TARGET_DIR/.venv/bin/activate"
python "$TARGET_DIR/src/run.py"
EOF

chmod +x "$LAUNCH_SCRIPT"


# --- Create folder-opening helper ---
OPEN_SCRIPT="$BIN_DIR/gpt-image-folders"

echo "→ Creating folder opener script at $OPEN_SCRIPT"

cat > "$OPEN_SCRIPT" <<EOF
#!/bin/sh
open "$TARGET_DIR/images"
open "$TARGET_DIR/out"
open "$TARGET_DIR/out"
EOF

chmod +x "$OPEN_SCRIPT"

echo ""
echo "✨ Setup complete!"
echo "To start using the new commands immediately, run:"
echo "  exec zsh"
echo "or open a new terminal window"
echo ""
echo "You can now run:"
echo "👉 gpt-converter      # runs src/run.py"
echo "👉 gpt-image-folders  # opens images/ out/ and style/ folders"
echo ""
echo "✔ Installed successfully!"
