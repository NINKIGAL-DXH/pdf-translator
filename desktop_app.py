"""
PDF Translator — Alter's Edition
PyQt5 桌面版
"""
import sys
import os
import io
import json
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

# Fix encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Base paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

for p in [BUNDLE_DIR, os.path.join(BUNDLE_DIR, 'pdf2zh')]:
    if p not in sys.path:
        sys.path.insert(0, p)

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QProgressBar, QFileDialog,
    QFrame, QSizePolicy, QMessageBox, QLineEdit, QGroupBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QColor, QDragEnterEvent, QDropEvent, QFont, QIcon


# ============================================================
# Dark Theme Colors
# ============================================================
COLORS = {
    'bg': '#0F0F0F',
    'bg2': '#1A1A1A',
    'bg3': '#2A2A2A',
    'text': '#E5E5E5',
    'text2': '#999999',
    'accent': '#3B82F6',
    'accent2': '#8B5CF6',
    'ok': '#22C55E',
    'err': '#EF4444',
    'border': '#333333',
}

STYLE = f"""
QMainWindow {{
    background-color: {COLORS['bg']};
}}
QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
}}
QLabel {{
    background: transparent;
}}
QPushButton {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 16px;
    color: {COLORS['text']};
}}
QPushButton:hover {{
    border-color: {COLORS['accent']};
}}
QPushButton:disabled {{
    opacity: 0.3;
    color: #666;
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['accent']}, stop:1 {COLORS['accent2']});
    border: none;
    color: white;
    font-weight: bold;
    font-size: 14px;
    padding: 12px 24px;
}}
QPushButton#primary:hover {{
    opacity: 0.9;
}}
QPushButton#primary:disabled {{
    background: #333;
    color: #666;
}}
QComboBox {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text']};
}}
QComboBox:hover {{
    border-color: {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    color: {COLORS['text']};
    selection-background-color: {COLORS['accent']};
}}
QLineEdit {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text']};
}}
QLineEdit:focus {{
    border-color: {COLORS['accent']};
}}
QProgressBar {{
    background-color: {COLORS['bg2']};
    border: none;
    border-radius: 5px;
    text-align: center;
    color: {COLORS['text']};
    height: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['accent']}, stop:1 {COLORS['accent2']});
    border-radius: 5px;
}}
QGroupBox {{
    background-color: {COLORS['bg2']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    margin-top: 10px;
    padding-top: 15px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 15px;
    padding: 0 5px;
}}
"""


# ============================================================
# Translation Engine
# ============================================================
class TranslatorEngine:
    def __init__(self):
        self.config = {
            'api_url': 'http://127.0.0.1:1234/v1',
            'model': 'google/gemma-4-26b-a4b',
            'lang_in': 'en',
            'lang_out': 'zh',
        }
        self.state = {
            'running': False, 'progress': 0, 'status': 'idle',
            'error': None, 'output_file': None,
            'current_page': 0, 'total_pages': 0,
        }
        self.upload_dir = os.path.join(BASE_DIR, 'uploads')
        self.output_dir = os.path.join(BASE_DIR, 'outputs')
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def translate(self, pdf_path, callback=None):
        self.state = {
            'running': True, 'progress': 0, 'status': 'starting',
            'error': None, 'output_file': None,
            'current_page': 0, 'total_pages': 0,
        }
        job_dir = os.path.join(self.output_dir, datetime.now().strftime('%Y%m%d_%H%M%S'))
        os.makedirs(job_dir, exist_ok=True)
        try:
            os.environ['OPENAILIKED_BASE_URL'] = self.config['api_url']
            os.environ['OPENAILIKED_API_KEY'] = 'not-needed'
            os.environ['OPENAILIKED_MODEL'] = self.config['model']

            import pymupdf
            from pdf2zh.high_level import translate
            from pdf2zh.doclayout import OnnxModel, get_doclayout_onnx_model_path

            model = OnnxModel(get_doclayout_onnx_model_path())
            doc = pymupdf.open(pdf_path)
            total = len(doc)
            doc.close()

            page_files = []
            for i in range(total):
                if not self.state['running']:
                    self.state['status'] = 'cancelled'
                    if callback:
                        callback(self.state)
                    return None
                self.state.update(current_page=i + 1, total_pages=total, progress=int((i + 1) / total * 90), status='translating')
                if callback:
                    callback(self.state)

                page_out = os.path.join(job_dir, f'page_{i}')
                os.makedirs(page_out, exist_ok=True)
                result = translate(
                    files=[pdf_path], output=page_out,
                    lang_in=self.config['lang_in'], lang_out=self.config['lang_out'],
                    service='openailiked', thread=1, model=model, pages=[i],
                )
                if result:
                    dest = os.path.join(job_dir, f'mono_p{i}.pdf')
                    shutil.copy2(result[0][0], dest)
                    page_files.append(dest)

            self.state.update(status='merging', progress=95)
            if callback:
                callback(self.state)

            merged = pymupdf.open()
            for i, f in enumerate(page_files):
                if os.path.exists(f):
                    src = pymupdf.open(f)
                    merged.insert_pdf(src, from_page=i, to_page=i)
                    src.close()
            output_path = os.path.join(job_dir, f'{Path(pdf_path).stem}-translated.pdf')
            merged.save(output_path)
            merged.close()

            self.state.update(status='done', output_file=output_path, progress=100)
            if callback:
                callback(self.state)
            return output_path
        except Exception as e:
            self.state.update(status='error', error=str(e))
            if callback:
                callback(self.state)
            return None

    def cancel(self):
        self.state['running'] = False


# ============================================================
# Translation Thread
# ============================================================
class TranslateThread(QThread):
    progress = pyqtSignal(dict)

    def __init__(self, engine, pdf_path):
        super().__init__()
        self.engine = engine
        self.pdf_path = pdf_path

    def run(self):
        self.engine.translate(self.pdf_path, callback=lambda s: self.progress.emit(s))


# ============================================================
# Drop Zone Widget
# ============================================================
class DropZone(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS['border']};
                border-radius: 16px;
                background-color: {COLORS['bg2']};
            }}
            QFrame:hover {{
                border-color: {COLORS['accent']};
                background-color: rgba(59, 130, 246, 0.03);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("PDF")
        icon.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {COLORS['accent']}; border: none;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        self.label = QLabel("Drop PDF here or click to browse")
        self.label.setStyleSheet(f"color: {COLORS['text2']}; font-size: 13px; border: none;")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            self.fileDropped.emit(path)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {COLORS['accent']};
                    border-radius: 16px;
                    background-color: rgba(59, 130, 246, 0.05);
                }}
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {COLORS['border']};
                border-radius: 16px;
                background-color: {COLORS['bg2']};
            }}
            QFrame:hover {{
                border-color: {COLORS['accent']};
                background-color: rgba(59, 130, 246, 0.03);
            }}
        """)

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.endswith('.pdf'):
                self.fileDropped.emit(path)
                break
        self.dragLeaveEvent(None)


# ============================================================
# Main Window
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.engine = TranslatorEngine()
        self.thread = None
        self.selected_file = None

        self.setWindowTitle("PDF Translator — Alter's Edition")
        self.setMinimumSize(600, 700)
        self.resize(650, 750)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(15)

        # Header
        header = QLabel("PDF Translator")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLORS['accent']};")
        main_layout.addWidget(header)

        subtitle = QLabel("Alter's Edition — Local PDF Translation")
        subtitle.setStyleSheet(f"color: {COLORS['text2']}; font-size: 12px; margin-bottom: 10px;")
        main_layout.addWidget(subtitle)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self.on_file_selected)
        main_layout.addWidget(self.drop_zone)

        # File info (hidden)
        self.file_info = QFrame()
        self.file_info.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg2']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        file_layout = QHBoxLayout(self.file_info)
        self.file_name_label = QLabel("")
        self.file_name_label.setStyleSheet("font-weight: bold; font-size: 13px; border: none;")
        self.file_size_label = QLabel("")
        self.file_size_label.setStyleSheet(f"color: {COLORS['text2']}; font-size: 12px; border: none;")
        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(28, 28)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['err']};
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: rgba(239, 68, 68, 0.1);
                border-radius: 4px;
            }}
        """)
        remove_btn.clicked.connect(self.remove_file)
        file_layout.addWidget(self.file_name_label)
        file_layout.addWidget(self.file_size_label)
        file_layout.addStretch()
        file_layout.addWidget(remove_btn)
        self.file_info.hide()
        main_layout.addWidget(self.file_info)

        # Settings
        settings_group = QGroupBox("Translation Settings")
        settings_layout = QVBoxLayout(settings_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("From:"))
        self.lang_in = QComboBox()
        self.lang_in.addItems(['English', 'Chinese', 'Japanese', 'Korean', 'French', 'German'])
        self.lang_in.setCurrentText('English')
        row1.addWidget(self.lang_in)
        row1.addWidget(QLabel("To:"))
        self.lang_out = QComboBox()
        self.lang_out.addItems(['Chinese', 'English', 'Japanese', 'Korean'])
        self.lang_out.setCurrentText('Chinese')
        row1.addWidget(self.lang_out)
        settings_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("API:"))
        self.api_url = QLineEdit("http://127.0.0.1:1234/v1")
        self.api_url.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        row2.addWidget(self.api_url)
        settings_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Model:"))
        self.model_name = QLineEdit("google/gemma-4-26b-a4b")
        self.model_name.setStyleSheet(f"font-family: 'JetBrains Mono', monospace; font-size: 11px;")
        row3.addWidget(self.model_name)
        settings_layout.addLayout(row3)

        main_layout.addWidget(settings_group)

        # Translate button
        self.translate_btn = QPushButton("Translate")
        self.translate_btn.setObjectName("primary")
        self.translate_btn.setEnabled(False)
        self.translate_btn.clicked.connect(self.start_translation)
        main_layout.addWidget(self.translate_btn)

        # Progress
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg2']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px;
            }}
        """)
        prog_layout = QVBoxLayout(self.progress_frame)

        prog_top = QHBoxLayout()
        self.progress_label = QLabel("Starting...")
        self.progress_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 12px; border: none;")
        self.progress_pct = QLabel("0%")
        self.progress_pct.setStyleSheet(f"color: {COLORS['accent']}; font-size: 12px; font-weight: bold; border: none;")
        prog_top.addWidget(self.progress_label)
        prog_top.addStretch()
        prog_top.addWidget(self.progress_pct)
        prog_layout.addLayout(prog_top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        prog_layout.addWidget(self.progress_bar)

        self.progress_pages = QLabel("")
        self.progress_pages.setStyleSheet(f"color: {COLORS['text2']}; font-size: 11px; border: none;")
        prog_layout.addWidget(self.progress_pages)

        self.progress_frame.hide()
        main_layout.addWidget(self.progress_frame)

        # Result
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(34, 197, 94, 0.05);
                border: 1px solid rgba(34, 197, 94, 0.2);
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        result_layout = QVBoxLayout(self.result_frame)
        result_label = QLabel("Translation Complete!")
        result_label.setStyleSheet(f"color: {COLORS['ok']}; font-weight: bold; font-size: 14px; border: none;")
        result_layout.addWidget(result_label)
        download_btn = QPushButton("Download PDF")
        download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(34, 197, 94, 0.1);
                border: 1px solid rgba(34, 197, 94, 0.3);
                color: {COLORS['ok']};
                font-weight: bold;
                padding: 10px;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: rgba(34, 197, 94, 0.2);
            }}
        """)
        download_btn.clicked.connect(self.download_result)
        result_layout.addWidget(download_btn)
        self.result_frame.hide()
        main_layout.addWidget(self.result_frame)

        # Error
        self.error_frame = QFrame()
        self.error_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(239, 68, 68, 0.05);
                border: 1px solid rgba(239, 68, 68, 0.2);
                border-radius: 10px;
                padding: 15px;
            }}
        """)
        error_layout = QVBoxLayout(self.error_frame)
        self.error_label = QLabel("Error")
        self.error_label.setStyleSheet(f"color: {COLORS['err']}; font-weight: bold; border: none;")
        error_layout.addWidget(self.error_label)
        self.error_frame.hide()
        main_layout.addWidget(self.error_frame)

        # Footer
        footer = QLabel("Made with lightning by Alter")
        footer.setStyleSheet(f"color: {COLORS['text2']}; font-size: 10px; border: none;")
        footer.setAlignment(Qt.AlignCenter)
        main_layout.addStretch()
        main_layout.addWidget(footer)

    def on_file_selected(self, path):
        self.selected_file = path
        name = os.path.basename(path)
        size = os.path.getsize(path) / 1024 / 1024
        self.file_name_label.setText(name)
        self.file_size_label.setText(f"{size:.1f} MB")
        self.drop_zone.hide()
        self.file_info.show()
        self.translate_btn.setEnabled(True)

    def remove_file(self):
        self.selected_file = None
        self.file_info.hide()
        self.drop_zone.show()
        self.translate_btn.setEnabled(False)
        self.result_frame.hide()
        self.error_frame.hide()
        self.progress_frame.hide()

    def start_translation(self):
        if not self.selected_file:
            return

        lang_map = {'English': 'en', 'Chinese': 'zh', 'Japanese': 'ja', 'Korean': 'ko', 'French': 'fr', 'German': 'de'}
        self.engine.config['api_url'] = self.api_url.text()
        self.engine.config['model'] = self.model_name.text()
        self.engine.config['lang_in'] = lang_map.get(self.lang_in.currentText(), 'en')
        self.engine.config['lang_out'] = lang_map.get(self.lang_out.currentText(), 'zh')

        self.translate_btn.setEnabled(False)
        self.translate_btn.setText("Translating...")
        self.result_frame.hide()
        self.error_frame.hide()
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting...")
        self.progress_pct.setText("0%")
        self.progress_pages.setText("")

        self.thread = TranslateThread(self.engine, self.selected_file)
        self.thread.progress.connect(self.on_progress)
        self.thread.start()

    def on_progress(self, state):
        pct = state.get('progress', 0)
        self.progress_bar.setValue(pct)
        self.progress_pct.setText(f"{pct}%")

        status = state.get('status', '')
        if status == 'translating':
            cp = state.get('current_page', 0)
            tp = state.get('total_pages', 0)
            self.progress_label.setText(f"Translating page {cp}/{tp}...")
            self.progress_pages.setText(f"Page {cp} of {tp}")
        elif status == 'merging':
            self.progress_label.setText("Merging pages...")
        elif status == 'done':
            self.progress_frame.hide()
            self.result_frame.show()
            self.reset_btn()
        elif status == 'error':
            self.progress_frame.hide()
            self.error_label.setText(f"Error: {state.get('error', 'Unknown')[:200]}")
            self.error_frame.show()
            self.reset_btn()
        elif status == 'cancelled':
            self.progress_frame.hide()
            self.reset_btn()

    def reset_btn(self):
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("Translate")

    def download_result(self):
        output = self.engine.state.get('output_file')
        if output and os.path.exists(output):
            save_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", os.path.basename(output), "PDF Files (*.pdf)")
            if save_path:
                shutil.copy2(output, save_path)
                QMessageBox.information(self, "Done", f"Saved to:\n{save_path}")

    def closeEvent(self, event):
        self.engine.cancel()
        event.accept()


# ============================================================
# Main
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)

    # Set font
    font = QFont()
    font.setPointSize(11)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
