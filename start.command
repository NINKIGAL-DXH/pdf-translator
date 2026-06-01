#!/bin/bash
# ============================================================
# PDF Translator — Alter's Edition
# macOS Launcher (参考 pdf2zhByGemini 的 start-mac.command)
# ============================================================

cd "$(dirname "$0")"
clear

echo "=========================================================="
echo "      PDF Translator — Alter's Edition"
echo "=========================================================="
echo ""

# Step 1: Check for Python 3 (need < 3.14 for onnxruntime)
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" > /dev/null 2>&1; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" = "3" ] && [ "$minor" -lt 14 ] 2>/dev/null; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[!] Compatible Python not found (need 3.11-3.13)."
    echo ""
    echo "    Your system has: $(python3 --version 2>&1)"
    echo "    This app requires Python 3.12 or 3.13."
    echo ""
    echo "    Attempting to install Python 3.12 via Homebrew..."
    echo ""
    
    if command -v brew > /dev/null 2>&1; then
        echo "[+] Homebrew found! Installing Python 3.12..."
        brew install python@3.12
        PYTHON="python3.12"
    else
        echo "[!] Homebrew not found."
        echo ""
        echo "    Option 1: Install Homebrew first:"
        echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        echo ""
        echo "    Option 2: Download Python 3.12 directly:"
        echo "    https://www.python.org/downloads/macos/"
        echo ""
        echo "Press any key to open the Python download page, or CTRL+C to cancel..."
        read -n 1 -r
        open "https://www.python.org/downloads/macos/"
        exit 1
    fi
fi

echo "[+] Using Python: $PYTHON ($($PYTHON --version 2>&1))"
echo ""

# Step 2: Install dependencies
echo "[+] Checking dependencies..."
MISSING=""
for pkg in flask pymupdf openai requests tqdm tenacity numpy onnxruntime; do
    imp="$pkg"
    [ "$pkg" = "pymupdf" ] && imp="fitz"
    if ! $PYTHON -c "import $imp" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    echo "[+] Installing missing packages:$MISSING"
    echo "    (This may take a few minutes on first run...)"
    $PYTHON -m pip install $MISSING --quiet
    echo "[+] Done!"
else
    echo "[+] All dependencies OK."
fi
echo ""

# Step 3: Check port
PORT=5050
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "[!] Port $PORT is already in use."
    echo "    Opening browser..."
    open "http://localhost:$PORT"
    exit 0
fi

# Step 4: Start server
echo "=========================================================="
echo "  Starting PDF Translator..."
echo "  Web GUI: http://localhost:$PORT"
echo "  Keep this Terminal window open while using the app."
echo "=========================================================="
echo ""

# Open browser after delay
(sleep 3; open "http://localhost:$PORT") &

# Run Flask
export PYTHONIOENCODING=utf-8
$PYTHON app.py
