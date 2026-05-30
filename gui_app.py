"""
PDF Translator — Alter's Edition
原生 GUI 版本（tkinter，跨平台）
"""
import sys
import os
import io
import threading
import shutil
import time
from pathlib import Path
from datetime import datetime

# Fix encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Paths
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

for p in [BUNDLE_DIR, os.path.join(BUNDLE_DIR, 'pdf2zh')]:
    if p not in sys.path:
        sys.path.insert(0, p)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
            'running': False,
            'progress': 0,
            'status': 'idle',
            'error': None,
            'output_file': None,
        }
        self.upload_dir = os.path.join(BASE_DIR, 'uploads')
        self.output_dir = os.path.join(BASE_DIR, 'outputs')
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def get_models(self):
        try:
            import requests
            r = requests.get(f"{self.config['api_url']}/models", timeout=5)
            if r.status_code == 200:
                return [m['id'] for m in r.json().get('data', [])]
        except:
            pass
        return [self.config['model']]

    def translate(self, pdf_path, callback=None):
        """Run translation in background thread."""
        self.state = {'running': True, 'progress': 0, 'status': 'starting', 'error': None, 'output_file': None}

        job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_dir = os.path.join(self.output_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)

        try:
            os.environ['OPENAILIKED_BASE_URL'] = self.config['api_url']
            os.environ['OPENAILIKED_API_KEY'] = 'not-needed'
            os.environ['OPENAILIKED_MODEL'] = self.config['model']

            import pymupdf
            from pdf2zh.high_level import translate
            from pdf2zh.doclayout import OnnxModel
            from babeldoc.assets.assets import get_doclayout_onnx_model_path

            model = OnnxModel(get_doclayout_onnx_model_path())
            doc = pymupdf.open(pdf_path)
            total = len(doc)
            doc.close()

            self.state['status'] = 'translating'
            self.state['total_pages'] = total

            page_files = []
            for i in range(total):
                if not self.state['running']:
                    self.state['status'] = 'cancelled'
                    return None

                self.state['current_page'] = i + 1
                self.state['progress'] = int((i + 1) / total * 90)
                if callback:
                    callback(self.state)

                page_out = os.path.join(job_dir, f'page_{i}')
                os.makedirs(page_out, exist_ok=True)

                result = translate(
                    files=[pdf_path],
                    output=page_out,
                    lang_in=self.config['lang_in'],
                    lang_out=self.config['lang_out'],
                    service='openailiked',
                    thread=1,
                    model=model,
                    pages=[i],
                )

                if result:
                    dest = os.path.join(job_dir, f'mono_p{i}.pdf')
                    shutil.copy2(result[0][0], dest)
                    page_files.append(dest)

            # Merge
            self.state['status'] = 'merging'
            self.state['progress'] = 95
            if callback:
                callback(self.state)

            merged = pymupdf.open()
            for i, f in enumerate(page_files):
                if os.path.exists(f):
                    src = pymupdf.open(f)
                    merged.insert_pdf(src, from_page=i, to_page=i)
                    src.close()

            basename = Path(pdf_path).stem
            output_path = os.path.join(job_dir, f'{basename}-translated.pdf')
            merged.save(output_path)
            merged.close()

            self.state['status'] = 'done'
            self.state['output_file'] = output_path
            self.state['progress'] = 100
            if callback:
                callback(self.state)
            return output_path

        except Exception as e:
            self.state['status'] = 'error'
            self.state['error'] = str(e)
            if callback:
                callback(self.state)
            return None

    def cancel(self):
        self.state['running'] = False


# ============================================================
# GUI
# ============================================================
class TranslatorApp:
    def __init__(self):
        self.engine = TranslatorEngine()
        self.selected_file = None

        # Create main window
        self.root = tk.Tk()
        self.root.title("PDF Translator — Alter's Edition")
        self.root.geometry("520x480")
        self.root.resizable(False, False)

        # Dark theme colors
        self.bg = '#1a1a2e'
        self.fg = '#e0e0e0'
        self.accent = '#6c5ce7'
        self.surface = '#16213e'
        self.root.configure(bg=self.bg)

        self._build_ui()

    def _build_ui(self):
        # Title
        title = tk.Label(self.root, text="PDF Translator", font=('SF Pro Display', 24, 'bold'),
                         bg=self.bg, fg=self.accent)
        title.pack(pady=(20, 5))

        subtitle = tk.Label(self.root, text="Alter's Edition", font=('SF Pro Text', 12),
                            bg=self.bg, fg='#888')
        subtitle.pack(pady=(0, 20))

        # File selection
        file_frame = tk.Frame(self.root, bg=self.surface, highlightbackground=self.accent,
                              highlightthickness=1, padx=15, pady=10)
        file_frame.pack(padx=30, fill='x')

        self.file_label = tk.Label(file_frame, text="选择 PDF 文件...", font=('SF Pro Text', 11),
                                   bg=self.surface, fg='#888', anchor='w')
        self.file_label.pack(side='left', fill='x', expand=True)

        browse_btn = tk.Button(file_frame, text="浏览", command=self._browse,
                               bg=self.accent, fg='white', font=('SF Pro Text', 10, 'bold'),
                               relief='flat', padx=15, pady=3)
        browse_btn.pack(side='right')

        # Settings
        settings_frame = tk.LabelFrame(self.root, text=" 设置 ", font=('SF Pro Text', 10),
                                       bg=self.surface, fg=self.fg, padx=15, pady=10)
        settings_frame.pack(padx=30, fill='x', pady=(10, 0))

        # API URL
        tk.Label(settings_frame, text="API 地址:", bg=self.surface, fg=self.fg,
                 font=('SF Pro Text', 10)).grid(row=0, column=0, sticky='w', pady=2)
        self.api_entry = tk.Entry(settings_frame, width=40, font=('SF Mono', 10),
                                  bg='#0f0f23', fg=self.fg, insertbackground=self.fg)
        self.api_entry.insert(0, self.engine.config['api_url'])
        self.api_entry.grid(row=0, column=1, sticky='w', padx=(10, 0), pady=2)

        # Model
        tk.Label(settings_frame, text="模型:", bg=self.surface, fg=self.fg,
                 font=('SF Pro Text', 10)).grid(row=1, column=0, sticky='w', pady=2)
        self.model_var = tk.StringVar(value=self.engine.config['model'])
        self.model_entry = tk.Entry(settings_frame, textvariable=self.model_var, width=40,
                                    font=('SF Mono', 10), bg='#0f0f23', fg=self.fg, insertbackground=self.fg)
        self.model_entry.grid(row=1, column=1, sticky='w', padx=(10, 0), pady=2)

        # Language
        lang_frame = tk.Frame(settings_frame, bg=self.surface)
        lang_frame.grid(row=2, column=0, columnspan=2, sticky='w', pady=2)

        tk.Label(lang_frame, text="从:", bg=self.surface, fg=self.fg).pack(side='left')
        self.lang_in_var = tk.StringVar(value='en')
        lang_in = ttk.Combobox(lang_frame, textvariable=self.lang_in_var, values=['en', 'zh', 'ja', 'ko', 'fr', 'de'],
                               width=8, state='readonly')
        lang_in.pack(side='left', padx=(5, 15))

        tk.Label(lang_frame, text="翻译为:", bg=self.surface, fg=self.fg).pack(side='left')
        self.lang_out_var = tk.StringVar(value='zh')
        lang_out = ttk.Combobox(lang_frame, textvariable=self.lang_out_var, values=['zh', 'en', 'ja', 'ko', 'fr', 'de'],
                                width=8, state='readonly')
        lang_out.pack(side='left', padx=(5, 0))

        # Translate button
        self.translate_btn = tk.Button(self.root, text="开始翻译", command=self._start_translate,
                                       bg=self.accent, fg='white', font=('SF Pro Text', 14, 'bold'),
                                       relief='flat', padx=40, pady=8, state='disabled')
        self.translate_btn.pack(pady=(20, 10))

        # Progress
        self.progress_var = tk.DoubleVar(value=0)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('Custom.Horizontal.TProgressbar', troughcolor='#0f0f23',
                        background=self.accent, darkcolor=self.accent, lightcolor=self.accent)
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100,
                                            style='Custom.Horizontal.TProgressbar', length=460)
        self.progress_bar.pack(padx=30)

        # Status label
        self.status_label = tk.Label(self.root, text="就绪", font=('SF Pro Text', 10),
                                     bg=self.bg, fg='#888')
        self.status_label.pack(pady=(5, 0))

        # Download button (hidden by default)
        self.download_btn = tk.Button(self.root, text="下载翻译结果", command=self._download,
                                      bg='#27ae60', fg='white', font=('SF Pro Text', 11, 'bold'),
                                      relief='flat', padx=20, pady=5)

    def _browse(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filepath:
            self.selected_file = filepath
            name = os.path.basename(filepath)
            self.file_label.config(text=name, fg=self.fg)
            self.translate_btn.config(state='normal')

    def _start_translate(self):
        if not self.selected_file:
            return

        # Update config
        self.engine.config['api_url'] = self.api_entry.get()
        self.engine.config['model'] = self.model_var.get()
        self.engine.config['lang_in'] = self.lang_in_var.get()
        self.engine.config['lang_out'] = self.lang_out_var.get()

        # Disable UI
        self.translate_btn.config(state='disabled', text='翻译中...')
        self.download_btn.pack_forget()
        self.progress_var.set(0)

        # Start translation in background
        def run():
            self.engine.translate(self.selected_file, callback=self._update_progress)

        threading.Thread(target=run, daemon=True).start()

    def _update_progress(self, state):
        """Called from background thread."""
        self.root.after(0, self._refresh_ui, state)

    def _refresh_ui(self, state):
        """Update UI in main thread."""
        self.progress_var.set(state['progress'])

        status = state['status']
        if status == 'translating':
            page = state.get('current_page', 0)
            total = state.get('total_pages', 0)
            self.status_label.config(text=f"翻译中... 第 {page}/{total} 页", fg='#e0e0e0')
        elif status == 'merging':
            self.status_label.config(text="合并中...", fg='#e0e0e0')
        elif status == 'done':
            self.status_label.config(text="翻译完成！", fg='#27ae60')
            self.translate_btn.config(state='normal', text='开始翻译')
            self.download_btn.pack(pady=(10, 0))
        elif status == 'error':
            err = state.get('error', '未知错误')
            self.status_label.config(text=f"错误: {err[:60]}", fg='#e74c3c')
            self.translate_btn.config(state='normal', text='开始翻译')
        elif status == 'cancelled':
            self.status_label.config(text="已取消", fg='#888')
            self.translate_btn.config(state='normal', text='开始翻译')

    def _download(self):
        output = self.engine.state.get('output_file')
        if output and os.path.exists(output):
            save_path = filedialog.asksaveasfilename(
                defaultextension='.pdf',
                filetypes=[("PDF files", "*.pdf")],
                initialfile=os.path.basename(output)
            )
            if save_path:
                shutil.copy2(output, save_path)
                messagebox.showinfo("完成", f"已保存到:\n{save_path}")

    def run(self):
        self.root.mainloop()


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    app = TranslatorApp()
    app.run()
