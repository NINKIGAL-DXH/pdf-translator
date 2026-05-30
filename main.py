"""
PDF Translator — Alter's Edition
打包入口脚本 (PyInstaller)
"""
import sys
import os
import webbrowser
import threading
import time

# Suppress console encoding issues
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Determine base path
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# Add paths
for p in [BUNDLE_DIR, os.path.join(BUNDLE_DIR, 'pdf2zh')]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Set environment
os.environ['OPENAILIKED_BASE_URL'] = 'http://127.0.0.1:1234/v1'
os.environ['OPENAILIKED_API_KEY'] = 'not-needed'

def open_browser():
    time.sleep(5)
    webbrowser.open('http://localhost:5000')

def main():
    # Open browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Suppress Flask/click output to avoid encoding errors
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    from app import app
    
    # Wait a moment for port to be free
    time.sleep(1)
    
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
