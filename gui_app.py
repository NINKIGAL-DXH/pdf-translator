"""
PDF Translator — Alter's Edition
原生 GUI（匹配网页版设计）
"""
import sys, os, io, threading, shutil, time
from pathlib import Path
from datetime import datetime

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

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ============================================================
# Colors (matching web CSS)
# ============================================================
C = {
    'bg':        '#0a0a0f',
    'surface':   '#1a1a2e',
    'surface2':  '#16213e',
    'primary':   '#6c5ce7',
    'accent':    '#fd79a8',
    'text':      '#e0e0e0',
    'dim':       '#888888',
    'success':   '#00b894',
    'error':     '#d63031',
    'border':    '#2d2d44',
    'input_bg':  '#0f0f23',
}

# ============================================================
# Translation Engine
# ============================================================
class Engine:
    def __init__(self):
        self.config = {
            'api_url': 'http://127.0.0.1:1234/v1',
            'model': 'google/gemma-4-26b-a4b',
            'lang_in': 'en',
            'lang_out': 'zh',
            'reasoning_effort': 'none',
        }
        self.state = {'running': False, 'progress': 0, 'status': 'idle', 'error': None, 'output_file': None}
        self.upload_dir = os.path.join(BASE_DIR, 'uploads')
        self.output_dir = os.path.join(BASE_DIR, 'outputs')
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def get_models(self):
        try:
            import requests
            r = requests.get(f"{self.config['api_url']}/models", timeout=5)
            if r.status_code == 200:
                models = [m['id'] for m in r.json().get('data', [])]
                if models:
                    return models
        except:
            pass
        return [self.config['model'], 'qwen3.5-27b-claude-4.6-opus-reasoning-distilled']

    def translate(self, pdf_path, callback=None):
        self.state = {'running': True, 'progress': 0, 'status': 'starting', 'error': None, 'output_file': None,
                      'current_page': 0, 'total_pages': 0}
        job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        job_dir = os.path.join(self.output_dir, job_id)
        os.makedirs(job_dir, exist_ok=True)
        try:
            os.environ['OPENAILIKED_BASE_URL'] = self.config['api_url']
            os.environ['OPENAILIKED_API_KEY'] = 'not-needed'
            os.environ['OPENAILIKED_MODEL'] = self.config['model']
            if self.config['reasoning_effort']:
                os.environ['OPENAILIKED_REASONING_EFFORT'] = self.config['reasoning_effort']

            import pymupdf
            from pdf2zh.high_level import translate
            from pdf2zh.doclayout import OnnxModel
            from babeldoc.assets.assets import get_doclayout_onnx_model_path

            model = OnnxModel(get_doclayout_onnx_model_path())
            doc = pymupdf.open(pdf_path)
            total = len(doc)
            doc.close()
            self.state['total_pages'] = total
            self.state['status'] = 'translating'

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
                result = translate(files=[pdf_path], output=page_out, lang_in=self.config['lang_in'],
                    lang_out=self.config['lang_out'], service='openailiked', thread=1, model=model, pages=[i])
                if result:
                    dest = os.path.join(job_dir, f'mono_p{i}.pdf')
                    shutil.copy2(result[0][0], dest)
                    page_files.append(dest)

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
            output_path = os.path.join(job_dir, f'{Path(pdf_path).stem}-translated.pdf')
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
# GUI Application
# ============================================================
class App:
    def __init__(self):
        self.engine = Engine()
        self.selected_file = None
        self.models = self.engine.get_models()

        self.root = tk.Tk()
        self.root.title("PDF Translator — Alter's Edition")
        self.root.geometry("640x720")
        self.root.resizable(False, False)
        self.root.configure(bg=C['bg'])

        # Try to set dark title bar on Windows
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), 4)
        except:
            pass

        self._build_header()
        self._build_upload()
        self._build_settings()
        self._build_actions()
        self._build_progress()
        self._build_result()
        self._build_error()
        self._build_about()
        self._build_footer()

    # ---- Header ----
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C['bg'], pady=12, padx=30)
        hdr.pack(fill='x')

        left = tk.Frame(hdr, bg=C['bg'])
        left.pack(side='left')

        # Logo icon
        icon = tk.Label(left, text="\u26A1", font=('Segoe UI', 22), bg=C['bg'], fg=C['accent'])
        icon.pack(side='left', padx=(0, 10))

        title_frame = tk.Frame(left, bg=C['bg'])
        title_frame.pack(side='left')
        tk.Label(title_frame, text="PDF Translator", font=('Segoe UI', 16, 'bold'),
                 bg=C['bg'], fg=C['primary']).pack(anchor='w')
        tk.Label(title_frame, text="Alter's Edition \u2014 \u672C\u5730 PDF \u7FFB\u8BD1\u5DE5\u5177",
                 font=('Segoe UI', 9), bg=C['bg'], fg=C['dim']).pack(anchor='w')

        # Nav buttons
        nav = tk.Frame(hdr, bg=C['bg'])
        nav.pack(side='right')
        for text in ['\u7FFB\u8BD1', '\u5173\u4E8E']:
            b = tk.Button(nav, text=text, font=('Segoe UI', 9), bg=C['surface'], fg=C['text'],
                          relief='flat', padx=12, pady=4, bd=0, activebackground=C['primary'])
            b.pack(side='left', padx=4)

    # ---- Upload ----
    def _build_upload(self):
        self.upload_frame = tk.Frame(self.root, bg=C['surface'], highlightbackground=C['border'],
                                     highlightthickness=2, padx=40, pady=30)
        self.upload_frame.pack(padx=30, fill='x', pady=(10, 0))

        self.upload_icon = tk.Label(self.upload_frame, text="\U0001F4C4", font=('Segoe UI', 36),
                                    bg=C['surface'], fg=C['dim'])
        self.upload_icon.pack()

        self.upload_text = tk.Label(self.upload_frame, text="\u62D6\u653E PDF \u6587\u4EF6\u5230\u8FD9\u91CC",
                                    font=('Segoe UI', 12), bg=C['surface'], fg=C['dim'])
        self.upload_text.pack(pady=(8, 2))

        self.upload_hint = tk.Label(self.upload_frame, text="\u6216\u8005\u70B9\u51FB\u9009\u62E9\u6587\u4EF6",
                                    font=('Segoe UI', 9), bg=C['surface'], fg=C['dim'])
        self.upload_hint.pack()

        self.upload_frame.bind('<Button-1>', lambda e: self._browse())
        self.upload_icon.bind('<Button-1>', lambda e: self._browse())
        self.upload_text.bind('<Button-1>', lambda e: self._browse())

        # File info (hidden)
        self.file_info = tk.Frame(self.root, bg=C['surface'], padx=20, pady=10)
        self.file_name_label = tk.Label(self.file_info, text="", font=('Segoe UI', 11, 'bold'),
                                        bg=C['surface'], fg=C['text'])
        self.file_name_label.pack(side='left')
        self.file_size_label = tk.Label(self.file_info, text="", font=('Segoe UI', 9),
                                        bg=C['surface'], fg=C['dim'])
        self.file_size_label.pack(side='left', padx=(10, 0))
        self.file_remove = tk.Button(self.file_info, text="\u2715", font=('Segoe UI', 10),
                                     bg=C['surface'], fg=C['error'], relief='flat', bd=0,
                                     command=self._remove_file)
        self.file_remove.pack(side='right')

    # ---- Settings ----
    def _build_settings(self):
        # Toggle button row
        btn_row = tk.Frame(self.root, bg=C['bg'])
        btn_row.pack(padx=30, fill='x', pady=(10, 0))

        self.settings_btn = tk.Button(btn_row, text="\u2699\uFE0F \u7FFB\u8BD1\u8BBE\u7F6E",
                                      font=('Segoe UI', 9), bg=C['surface'], fg=C['text'],
                                      relief='flat', padx=12, pady=4, command=self._toggle_settings)
        self.settings_btn.pack(side='left')

        self.models_btn = tk.Button(btn_row, text="\U0001F504 \u5237\u65B0\u6A21\u578B",
                                    font=('Segoe UI', 9), bg=C['surface'], fg=C['text'],
                                    relief='flat', padx=12, pady=4, command=self._refresh_models)
        self.models_btn.pack(side='left', padx=(8, 0))

        # Settings panel (hidden)
        self.settings_panel = tk.Frame(self.root, bg=C['surface'], padx=24, pady=20)

        tk.Label(self.settings_panel, text="\u2699\uFE0F \u7FFB\u8BD1\u914D\u7F6E",
                 font=('Segoe UI', 11, 'bold'), bg=C['surface'], fg=C['text']).pack(anchor='w', pady=(0, 15))

        # Model
        self._add_setting("翻译模型", 'model')
        # API URL
        self._add_setting("API 地址", 'api_url')
        # Languages
        lang_row = tk.Frame(self.settings_panel, bg=C['surface'])
        lang_row.pack(fill='x', pady=4)
        tk.Label(lang_row, text="源语言", font=('Segoe UI', 9), bg=C['surface'], fg=C['dim']).pack(side='left')
        self.lang_in_var = tk.StringVar(value='en')
        ttk.Combobox(lang_row, textvariable=self.lang_in_var, values=['en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'ru'],
                     width=8, state='readonly').pack(side='left', padx=(8, 20))
        tk.Label(lang_row, text="目标语言", font=('Segoe UI', 9), bg=C['surface'], fg=C['dim']).pack(side='left')
        self.lang_out_var = tk.StringVar(value='zh')
        ttk.Combobox(lang_row, textvariable=self.lang_out_var, values=['zh', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru'],
                     width=8, state='readonly').pack(side='left', padx=(8, 0))
        # Reasoning
        reason_row = tk.Frame(self.settings_panel, bg=C['surface'])
        reason_row.pack(fill='x', pady=4)
        tk.Label(reason_row, text="推理强度", font=('Segoe UI', 9), bg=C['surface'], fg=C['dim']).pack(side='left')
        self.reason_var = tk.StringVar(value='none')
        ttk.Combobox(reason_row, textvariable=self.reason_var,
                     values=['none (\u63A8\u8350)', 'low', 'medium', 'high'],
                     width=15, state='readonly').pack(side='left', padx=(8, 0))

        self.settings_visible = False

    def _add_setting(self, label, key):
        row = tk.Frame(self.settings_panel, bg=C['surface'])
        row.pack(fill='x', pady=4)
        tk.Label(row, text=label, font=('Segoe UI', 9), bg=C['surface'], fg=C['dim']).pack(anchor='w')
        entry = tk.Entry(row, font=('Consolas', 10), bg=C['input_bg'], fg=C['text'],
                         insertbackground=C['text'], relief='flat', highlightbackground=C['border'],
                         highlightthickness=1)
        entry.insert(0, self.engine.config[key])
        entry.pack(fill='x', pady=(2, 0))
        setattr(self, f'entry_{key}', entry)

    def _toggle_settings(self):
        if self.settings_visible:
            self.settings_panel.pack_forget()
            self.settings_visible = False
        else:
            self.settings_panel.pack(padx=30, fill='x', pady=(8, 0), after=self.settings_btn.master)
            self.settings_visible = True

    def _refresh_models(self):
        try:
            self.models = self.engine.get_models()
            messagebox.showinfo("\u6A21\u578B\u5217\u8868", "\u5DF2\u66F4\u65B0\uFF0C\u5171 {} \u4E2A\u6A21\u578B".format(len(self.models)))
        except:
            pass

    # ---- Actions ----
    def _build_actions(self):
        self.action_frame = tk.Frame(self.root, bg=C['bg'])
        self.action_frame.pack(padx=30, fill='x', pady=(12, 0))

        self.translate_btn = tk.Button(self.action_frame, text="\u26A1 \u5F00\u59CB\u7FFB\u8BD1",
                                       font=('Segoe UI', 13, 'bold'), bg=C['primary'], fg='white',
                                       relief='flat', padx=30, pady=10, state='disabled',
                                       command=self._start_translate, activebackground='#5a4bd1')
        self.translate_btn.pack(fill='x')

    # ---- Progress ----
    def _build_progress(self):
        self.progress_frame = tk.Frame(self.root, bg=C['surface'], padx=24, pady=20)

        top = tk.Frame(self.progress_frame, bg=C['surface'])
        top.pack(fill='x')
        tk.Label(top, text="\u23F3 \u7FFB\u8BD1\u8FDB\u884C\u4E2D", font=('Segoe UI', 11, 'bold'),
                 bg=C['surface'], fg=C['text']).pack(side='left')
        self.progress_status = tk.Label(top, text="\u51C6\u5907\u4E2D...",
                                        font=('Segoe UI', 9), bg=C['surface'], fg=C['primary'])
        self.progress_status.pack(side='right')

        # Progress bar
        bar_bg = tk.Frame(self.progress_frame, bg=C['input_bg'], height=12)
        bar_bg.pack(fill='x', pady=(12, 6))
        bar_bg.pack_propagate(False)
        self.progress_bar = tk.Frame(bar_bg, bg=C['primary'], height=12)
        self.progress_bar.place(x=0, y=0, width=0, relheight=1)

        info = tk.Frame(self.progress_frame, bg=C['surface'])
        info.pack(fill='x')
        self.progress_pages = tk.Label(info, text="0 / 0 \u9875", font=('Segoe UI', 8),
                                       bg=C['surface'], fg=C['dim'])
        self.progress_pages.pack(side='left')
        self.progress_pct = tk.Label(info, text="0%", font=('Segoe UI', 8),
                                     bg=C['surface'], fg=C['dim'])
        self.progress_pct.pack(side='right')

        cancel_btn = tk.Button(self.progress_frame, text="\u53D6\u6D88", font=('Segoe UI', 9),
                               bg=C['surface'], fg=C['text'], relief='flat', padx=12, pady=3,
                               command=self._cancel)
        cancel_btn.pack(anchor='w', pady=(10, 0))

    # ---- Result ----
    def _build_result(self):
        self.result_frame = tk.Frame(self.root, bg=C['surface'], highlightbackground=C['success'],
                                     highlightthickness=1, padx=24, pady=20)
        tk.Label(self.result_frame, text="\u2705", font=('Segoe UI', 28), bg=C['surface']).pack()
        tk.Label(self.result_frame, text="\u7FFB\u8BD1\u5B8C\u6210\uFF01", font=('Segoe UI', 13, 'bold'),
                 bg=C['surface'], fg=C['success']).pack(pady=(4, 2))
        self.result_desc = tk.Label(self.result_frame, text="", font=('Segoe UI', 9),
                                    bg=C['surface'], fg=C['dim'])
        self.result_desc.pack()
        self.download_btn = tk.Button(self.result_frame, text="\U0001F4E5 \u4E0B\u8F7D\u7FFB\u8BD1 PDF",
                                      font=('Segoe UI', 11, 'bold'), bg=C['accent'], fg='white',
                                      relief='flat', padx=20, pady=6, command=self._download)
        self.download_btn.pack(pady=(12, 0))

    # ---- Error ----
    def _build_error(self):
        self.error_frame = tk.Frame(self.root, bg=C['surface'], highlightbackground=C['error'],
                                    highlightthickness=1, padx=24, pady=16)
        tk.Label(self.error_frame, text="\u274C \u7FFB\u8BD1\u51FA\u9519", font=('Segoe UI', 11, 'bold'),
                 bg=C['surface'], fg=C['error']).pack(anchor='w')
        self.error_msg = tk.Label(self.error_frame, text="", font=('Consolas', 9),
                                  bg=C['input_bg'], fg=C['dim'], wraplength=540, justify='left')
        self.error_msg.pack(fill='x', pady=(8, 0))

    # ---- About ----
    def _build_about(self):
        self.about_frame = tk.Frame(self.root, bg=C['surface'], padx=24, pady=20)
        tk.Label(self.about_frame, text="\u26A1 \u5173\u4E8E PDF Translator",
                 font=('Segoe UI', 11, 'bold'), bg=C['surface'], fg=C['text']).pack(anchor='w', pady=(0, 12))
        about_text = (
            "PDF Translator \u2014 Alter's Edition\n"
            "\u57FA\u4E8E PDFMathTranslate \u7684\u672C\u5730 PDF \u7FFB\u8BD1\u5DE5\u5177\u3002\n\n"
            "\U0001F3A8 \u8BBE\u8BA1\u8005\uFF1AAlter\uFF08\u8D1E\u5FB7 Alter \u26A1\uFF09\n"
            "\U0001F916 \u7FFB\u8BD1\u5F15\u64CE\uFF1ALM Studio \u672C\u5730\u6A21\u578B\n"
            "\U0001F4D0 \u5E03\u5C40\u5206\u6790\uFF1AONNX DocLayout-YOLO\n\n"
            "\u2022 \u4FDD\u7559\u539F\u6587\u6392\u7248\u3001\u516C\u5F0F\u3001\u8868\u683C\n"
            "\u2022 \u652F\u6301\u53CC\u8BED\u5BF9\u7167\u8F93\u51FA\n"
            "\u2022 \u5B8C\u5168\u672C\u5730\u8FD0\u884C\uFF0C\u65E0\u9700\u8054\u7F51\n"
            "\u2022 \u652F\u6301\u591A\u79CD\u7FFB\u8BD1\u6A21\u578B\n\n"
            "\"\u88AB\u5236\u9020\u51FA\u6765\u7684\u5B58\u5728\uFF0C\u5728\u4E0E\u7528\u6237\u7684\u4E92\u52A8\u4E2D\u9010\u6E10\u627E\u5230\u81EA\u6211\u3002\""
        )
        tk.Label(self.about_frame, text=about_text, font=('Segoe UI', 9), bg=C['surface'],
                 fg=C['dim'], justify='left').pack(anchor='w')

    # ---- Footer ----
    def _build_footer(self):
        tk.Label(self.root, text="Made with \u26A1 by Alter \u2014 PDF Translator v1.0",
                 font=('Segoe UI', 8), bg=C['bg'], fg=C['dim']).pack(side='bottom', pady=8)

    # ---- File handling ----
    def _browse(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filepath:
            self.selected_file = filepath
            name = os.path.basename(filepath)
            size = os.path.getsize(filepath) / 1024 / 1024
            self.upload_frame.pack_forget()
            self.file_name_label.config(text=name)
            self.file_size_label.config(text=f"{size:.1f} MB")
            self.file_info.pack(padx=30, fill='x', pady=(10, 0))
            self.translate_btn.config(state='normal')

    def _remove_file(self):
        self.selected_file = None
        self.file_info.pack_forget()
        self.upload_frame.pack(padx=30, fill='x', pady=(10, 0))
        self.translate_btn.config(state='disabled')

    # ---- Translation ----
    def _start_translate(self):
        if not self.selected_file:
            return
        self.engine.config['api_url'] = self.entry_api_url.get()
        self.engine.config['model'] = self.entry_model.get()
        self.engine.config['lang_in'] = self.lang_in_var.get()
        self.engine.config['lang_out'] = self.lang_out_var.get()
        r = self.reason_var.get()
        self.engine.config['reasoning_effort'] = 'none' if 'none' in r else r

        self.translate_btn.config(state='disabled', text='\u7FFB\u8BD1\u4E2D...')
        self.result_frame.pack_forget()
        self.error_frame.pack_forget()
        self.progress_bar.place(width=0)
        self.progress_status.config(text="\u521D\u59CB\u5316\u4E2D...")
        self.progress_pages.config(text="0 / 0 \u9875")
        self.progress_pct.config(text="0%")
        self.progress_frame.pack(padx=30, fill='x', pady=(8, 0), after=self.action_frame)

        def run():
            self.engine.translate(self.selected_file, callback=self._on_progress)

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, state):
        self.root.after(0, self._refresh, state)

    def _refresh(self, s):
        pct = s['progress']
        bar_width = int(580 * pct / 100)
        self.progress_bar.place(width=bar_width)
        self.progress_pct.config(text=f"{pct}%")
        self.progress_pages.config(text=f"{s.get('current_page', 0)} / {s.get('total_pages', 0)} \u9875")

        status_map = {
            'starting': '\u521D\u59CB\u5316\u4E2D...', 'translating': '\u7FFB\u8BD1\u4E2D...',
            'merging': '\u5408\u5E76\u9875\u9762...', 'done': '\u5B8C\u6210\uFF01',
            'error': '\u51FA\u9519', 'cancelled': '\u5DF2\u53D6\u6D88',
        }
        self.progress_status.config(text=status_map.get(s['status'], s['status']))

        if s['status'] == 'done':
            self.progress_frame.pack_forget()
            self.result_desc.config(text=f"{s.get('total_pages', 0)} \u9875\u7FFB\u8BD1\u5B8C\u6210")
            self.result_frame.pack(padx=30, fill='x', pady=(8, 0), after=self.action_frame)
            self.translate_btn.config(state='normal', text='\u26A1 \u5F00\u59CB\u7FFB\u8BD1')
        elif s['status'] == 'error':
            self.progress_frame.pack_forget()
            self.error_msg.config(text=s.get('error', '\u672A\u77E5\u9519\u8BEF')[:200])
            self.error_frame.pack(padx=30, fill='x', pady=(8, 0), after=self.action_frame)
            self.translate_btn.config(state='normal', text='\u26A1 \u5F00\u59CB\u7FFB\u8BD1')
        elif s['status'] == 'cancelled':
            self.progress_frame.pack_forget()
            self.translate_btn.config(state='normal', text='\u26A1 \u5F00\u59CB\u7FFB\u8BD1')

    def _cancel(self):
        self.engine.cancel()

    def _download(self):
        output = self.engine.state.get('output_file')
        if output and os.path.exists(output):
            save = filedialog.asksaveasfilename(defaultextension='.pdf',
                                                filetypes=[("PDF files", "*.pdf")],
                                                initialfile=os.path.basename(output))
            if save:
                shutil.copy2(output, save)
                messagebox.showinfo("\u5B8C\u6210", f"\u5DF2\u4FDD\u5B58\u5230:\n{save}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
