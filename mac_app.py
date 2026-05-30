"""
PDF Translator — Alter's Edition
macOS Menu Bar App + Web UI
"""
import sys
import os
import io
import threading
import webbrowser
import time

os.environ['PYTHONIOENCODING'] = 'utf-8'

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

for p in [BUNDLE_DIR, os.path.join(BUNDLE_DIR, 'pdf2zh')]:
    if p not in sys.path:
        sys.path.insert(0, p)

import rumps


class FlaskServer(threading.Thread):
    """Run Flask in background."""
    def __init__(self, app_module):
        super().__init__(daemon=True)
        self.app_module = app_module

    def run(self):
        self.app_module.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


class PDFTranslatorApp(rumps.App):
    def __init__(self):
        super().__init__(
            name="PDF Translator",
            title="PDF",
            quit_button=None,
        )
        self.server = None
        self.port = 5000

        # Menu items
        self.menu = [
            rumps.MenuItem("Open Web UI", callback=self.open_web),
            rumps.MenuItem("Start Server", callback=self.start_server),
            rumps.MenuItem("Stop Server", callback=self.stop_server),
            None,  # separator
            rumps.MenuItem("Settings", callback=self.show_settings),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Auto-start server
        self.start_server(None)

    def start_server(self, _):
        if self.server and self.server.is_alive():
            rumps.notification("PDF Translator", "", "Server already running")
            return

        try:
            import app as flask_app
            self.server = FlaskServer(flask_app)
            self.server.start()
            time.sleep(1)
            rumps.notification("PDF Translator", "", f"Server started on port {self.port}")
            self.title = "PDF"
        except Exception as e:
            rumps.notification("PDF Translator", "Error", str(e))

    def stop_server(self, _):
        # Flask doesn't have a clean shutdown, just notify
        rumps.notification("PDF Translator", "", "Server will stop when app quits")
        self.title = "PDF"

    def open_web(self, _):
        webbrowser.open(f"http://localhost:{self.port}")

    def show_settings(self, _):
        webbrowser.open(f"http://localhost:{self.port}")

    def quit_app(self, _):
        rumps.quit_application()


if __name__ == "__main__":
    PDFTranslatorApp().run()
