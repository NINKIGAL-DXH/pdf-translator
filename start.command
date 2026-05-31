#!/bin/bash
# ============================================================
# PDF Translator — Alter's Edition
# 双击运行此文件即可启动
# ============================================================

cd "$(dirname "$0")"

echo "=========================================="
echo " PDF Translator — Alter's Edition"
echo "=========================================="
echo ""

# Find Python
PYTHON=""
for cmd in python3 python /usr/bin/python3; do
    if command -v "$cmd" > /dev/null 2>&1; then
        ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" = "3" ]; then
            PYTHON="$cmd"
            echo "Found Python: $cmd ($ver)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3 not found!"
    echo "Please install: brew install python"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check Python version (need < 3.14 for babeldoc)
minor=$(echo "$ver" | cut -d. -f2)
if [ "$minor" -ge 14 ] 2>/dev/null; then
    echo ""
    echo "WARNING: Python $ver detected. babeldoc requires Python < 3.14."
    echo "Please install Python 3.12: brew install python@3.12"
    echo "Then run: python3.12 start.sh"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check and install dependencies
echo ""
echo "Checking dependencies..."
MISSING=""
for pkg in flask pymupdf openai requests tqdm tenacity numpy onnxruntime babeldoc; do
    imp="$pkg"; [ "$pkg" = "pymupdf" ] && imp="fitz"
    if ! $PYTHON -c "import $imp" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    echo "Installing missing packages:$MISSING"
    echo "(This may take a few minutes on first run...)"
    $PYTHON -m pip install $MISSING --quiet
    echo "Done!"
else
    echo "All dependencies OK."
fi

# Check port
if lsof -Pi :5050 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo ""
    echo "Port 5050 is in use. Opening browser..."
    open http://localhost:5050
    exit 0
fi

# Start
echo ""
echo "Starting PDF Translator..."
echo "Browser will open at: http://localhost:5050"
echo "Press Ctrl+C to stop."
echo ""

# Open browser after delay
(sleep 3; open http://localhost:5050) &

# Run Flask
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
$PYTHON app.py
