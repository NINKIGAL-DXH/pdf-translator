"""
PDF Translator - Alter's Edition
Cross-platform GUI (tkinter)
"""
import sys, os, threading, shutil, time
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
# Translation Engine
# ============================================================
class Engine:
    def __init__(self):
        self.config = {
            'api_url': 'http://127.0.0.1:1234/v1',
            'model': 'google/gemma-4-26b-a4b',
            'lang_in': 'en',
            'lang_out': 'zh',
        }
        self.state = {'running': False, 'progress': 0, 'status': 'idle', 'error': None, 'output_file': None}
        self.upload_dir = os.path.join(BASE_DIR, 'uploads')
        self.output_dir = os.path.join(BASE_DIR, 'outputs')
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def translate(self, pdf_path, callback=None):
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

            page_files = []
            for i in range(total):
                if not self.state['running']:
                    self.state['status'] = 'cancelled'
                    if callback: callback(self.state)
                    return None
                self.state['current_page'] = i + 1
                self.state['total_pages'] = total
                self.state['progress'] = int((i + 1) / total * 90)
                self.state['status'] = 'translating'
                if callback: callback(self.state)

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
            if callback: callback(self.state)

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
            if callback: callback(self.state)
            return output_path
        except Exception as e:
            self.state['status'] = 'error'
            self.state['error'] = str(e)
            if callback: callback(self.state)
            return None

    def cancel(self):
        self.state['running'] = False


# ============================================================
# GUI
# ============================================================
BG = '#0a0a0f'
SURFACE = '#1a1a2e'
PRIMARY = '#6c5ce7'
ACCENT = '#fd79a8'
TEXT = '#e0e0e0'
DIM = '#888888'
SUCCESS = '#00b894'
ERROR = '#d63031'
BORDER = '#2d2d44'
INPUT_BG = '#0f0f23'

FONT = 'Helvetica'
FONT_MONO = 'Courier'


class App:
    def __init__(self):
        self.engine = Engine()
        self.selected_file = None

        self.root = tk.Tk()
        self.root.title("PDF Translator")
        self.root.geometry("580x680")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Header
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill='x', padx=24, pady=(16, 8))
        tk.Label(hdr, text="PDF Translator", font=(FONT, 20, 'bold'), bg=BG, fg=PRIMARY).pack(side='left')
        tk.Label(hdr, text="Alter's Edition", font=(FONT, 10), bg=BG, fg=DIM).pack(side='left', padx=(10, 0), pady=(6, 0))

        # Separator
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill='x', padx=24)

        # Upload area
        self.upload_frame = tk.Frame(self.root, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        self.upload_frame.pack(fill='x', padx=24, pady=(16, 0))

        inner = tk.Frame(self.upload_frame, bg=SURFACE)
        inner.pack(pady=24)
        tk.Label(inner, text="PDF", font=(FONT, 28, 'bold'), bg=SURFACE, fg=PRIMARY).pack()
        tk.Label(inner, text="click to select file", font=(FONT, 10), bg=SURFACE, fg=DIM).pack(pady=(4, 0))

        self.upload_frame.bind('<Button-1>', lambda e: self._browse())
        for w in inner.winfo_children():
            w.bind('<Button-1>', lambda e: self._browse())
        inner.bind('<Button-1>', lambda e: self._browse())

        # File info (hidden initially)
        self.file_frame = tk.Frame(self.root, bg=SURFACE)
        self.file_label = tk.Label(self.file_frame, text="", font=(FONT, 11, 'bold'), bg=SURFACE, fg=TEXT)
        self.file_label.pack(side='left', padx=16)
        self.file_size = tk.Label(self.file_frame, text="", font=(FONT, 9), bg=SURFACE, fg=DIM)
        self.file_size.pack(side='left')
        tk.Button(self.file_frame, text="X", font=(FONT, 10), bg=SURFACE, fg=ERROR,
                  relief='flat', bd=0, command=self._remove).pack(side='right', padx=16)

        # Settings
        self.set_frame = tk.Frame(self.root, bg=SURFACE)
        # Model
        tk.Label(self.set_frame, text="Model", font=(FONT, 9), bg=SURFACE, fg=DIM).pack(anchor='w', padx=16, pady=(12, 0))
        self.model_entry = tk.Entry(self.set_frame, font=(FONT_MONO, 10), bg=INPUT_BG, fg=TEXT,
                                    insertbackground=TEXT, relief='flat')
        self.model_entry.insert(0, self.engine.config['model'])
        self.model_entry.pack(fill='x', padx=16, pady=(2, 0))
        # API URL
        tk.Label(self.set_frame, text="API URL", font=(FONT, 9), bg=SURFACE, fg=DIM).pack(anchor='w', padx=16, pady=(8, 0))
        self.api_entry = tk.Entry(self.set_frame, font=(FONT_MONO, 10), bg=INPUT_BG, fg=TEXT,
                                  insertbackground=TEXT, relief='flat')
        self.api_entry.insert(0, self.engine.config['api_url'])
        self.api_entry.pack(fill='x', padx=16, pady=(2, 0))
        # Languages
        lang = tk.Frame(self.set_frame, bg=SURFACE)
        lang.pack(fill='x', padx=16, pady=(8, 12))
        tk.Label(lang, text="From:", font=(FONT, 9), bg=SURFACE, fg=DIM).pack(side='left')
        self.lang_in = ttk.Combobox(lang, values=['en', 'zh', 'ja', 'ko', 'fr', 'de'], width=6, state='readonly')
        self.lang_in.set('en')
        self.lang_in.pack(side='left', padx=(4, 16))
        tk.Label(lang, text="To:", font=(FONT, 9), bg=SURFACE, fg=DIM).pack(side='left')
        self.lang_out = ttk.Combobox(lang, values=['zh', 'en', 'ja', 'ko', 'fr', 'de'], width=6, state='readonly')
        self.lang_out.set('zh')
        self.lang_out.pack(side='left', padx=(4, 0))

        # Settings toggle
        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(fill='x', padx=24, pady=(8, 0))
        self.set_btn = tk.Button(btn_row, text="Settings", font=(FONT, 9), bg=SURFACE, fg=TEXT,
                                 relief='flat', padx=12, pady=3, command=self._toggle_settings)
        self.set_btn.pack(side='left')
        self.set_visible = False

        # Translate button
        self.trans_btn = tk.Button(self.root, text="Translate", font=(FONT, 14, 'bold'),
                                   bg=PRIMARY, fg='white', relief='flat', padx=30, pady=10,
                                   state='disabled', command=self._translate)
        self.trans_btn.pack(fill='x', padx=24, pady=(12, 0))

        # Progress area
        self.prog_frame = tk.Frame(self.root, bg=SURFACE)
        self.prog_label = tk.Label(self.prog_frame, text="Preparing...", font=(FONT, 10),
                                   bg=SURFACE, fg=PRIMARY)
        self.prog_label.pack(anchor='w', padx=16, pady=(12, 4))
        bar_outer = tk.Frame(self.prog_frame, bg=INPUT_BG, height=10)
        bar_outer.pack(fill='x', padx=16)
        bar_outer.pack_propagate(False)
        self.bar = tk.Frame(bar_outer, bg=PRIMARY, height=10)
        self.bar.place(x=0, y=0, width=0, relheight=1)
        self.prog_info = tk.Label(self.prog_frame, text="0%", font=(FONT, 8), bg=SURFACE, fg=DIM)
        self.prog_info.pack(anchor='e', padx=16, pady=(2, 4))
        tk.Button(self.prog_frame, text="Cancel", font=(FONT, 9), bg=SURFACE, fg=TEXT,
                  relief='flat', padx=8, pady=2, command=self._cancel).pack(anchor='w', padx=16, pady=(0, 8))

        # Result area
        self.result_frame = tk.Frame(self.root, bg=SURFACE, highlightbackground=SUCCESS, highlightthickness=1)
        tk.Label(self.result_frame, text="Done!", font=(FONT, 16, 'bold'), bg=SURFACE, fg=SUCCESS).pack(pady=(16, 4))
        self.result_info = tk.Label(self.result_frame, text="", font=(FONT, 10), bg=SURFACE, fg=DIM)
        self.result_info.pack()
        tk.Button(self.result_frame, text="Save PDF", font=(FONT, 11, 'bold'), bg=ACCENT, fg='white',
                  relief='flat', padx=20, pady=6, command=self._download).pack(pady=(12, 16))

        # Error area
        self.err_frame = tk.Frame(self.root, bg=SURFACE, highlightbackground=ERROR, highlightthickness=1)
        tk.Label(self.err_frame, text="Error", font=(FONT, 12, 'bold'), bg=SURFACE, fg=ERROR).pack(anchor='w', padx=16, pady=(12, 4))
        self.err_msg = tk.Label(self.err_frame, text="", font=(FONT_MONO, 9), bg=INPUT_BG, fg=DIM,
                                wraplength=500, justify='left')
        self.err_msg.pack(fill='x', padx=16, pady=(0, 12))

        # Footer
        tk.Label(self.root, text="Made with lightning by Alter", font=(FONT, 8), bg=BG, fg=DIM).pack(side='bottom', pady=8)

    def _browse(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if f:
            self.selected_file = f
            name = os.path.basename(f)
            size = os.path.getsize(f) / 1024 / 1024
            self.upload_frame.pack_forget()
            self.file_label.config(text=name)
            self.file_size.config(text=f"{size:.1f} MB")
            self.file_frame.pack(fill='x', padx=24, pady=(16, 0))
            self.trans_btn.config(state='normal')

    def _remove(self):
        self.selected_file = None
        self.file_frame.pack_forget()
        self.upload_frame.pack(fill='x', padx=24, pady=(16, 0))
        self.trans_btn.config(state='disabled')

    def _toggle_settings(self):
        if self.set_visible:
            self.set_frame.pack_forget()
            self.set_visible = False
        else:
            self.set_frame.pack(fill='x', padx=24, pady=(8, 0), after=self.set_btn.master)
            self.set_visible = True

    def _translate(self):
        if not self.selected_file:
            return
        self.engine.config['api_url'] = self.api_entry.get()
        self.engine.config['model'] = self.model_entry.get()
        self.engine.config['lang_in'] = self.lang_in.get()
        self.engine.config['lang_out'] = self.lang_out.get()

        self.trans_btn.config(state='disabled', text='Translating...')
        self.result_frame.pack_forget()
        self.err_frame.pack_forget()
        self.bar.place(width=0)
        self.prog_label.config(text="Starting...")
        self.prog_info.config(text="0%")
        self.prog_frame.pack(fill='x', padx=24, pady=(8, 0), after=self.trans_btn)

        def run():
            self.engine.translate(self.selected_file, callback=self._on_progress)

        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, s):
        self.root.after(0, self._refresh, s)

    def _refresh(self, s):
        pct = s['progress']
        self.bar.place(width=int(520 * pct / 100))
        self.prog_info.config(text=f"{pct}%")

        if s['status'] == 'translating':
            cp = s.get('current_page', 0)
            tp = s.get('total_pages', 0)
            self.prog_label.config(text=f"Translating page {cp}/{tp}...")
        elif s['status'] == 'merging':
            self.prog_label.config(text="Merging pages...")
        elif s['status'] == 'done':
            self.prog_frame.pack_forget()
            tp = s.get('total_pages', 0)
            self.result_info.config(text=f"{tp} pages translated")
            self.result_frame.pack(fill='x', padx=24, pady=(8, 0), after=self.trans_btn)
            self.trans_btn.config(state='normal', text='Translate')
        elif s['status'] == 'error':
            self.prog_frame.pack_forget()
            self.err_msg.config(text=str(s.get('error', 'Unknown'))[:200])
            self.err_frame.pack(fill='x', padx=24, pady=(8, 0), after=self.trans_btn)
            self.trans_btn.config(state='normal', text='Translate')
        elif s['status'] == 'cancelled':
            self.prog_frame.pack_forget()
            self.trans_btn.config(state='normal', text='Translate')

    def _cancel(self):
        self.engine.cancel()

    def _download(self):
        out = self.engine.state.get('output_file')
        if out and os.path.exists(out):
            save = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[("PDF", "*.pdf")],
                                                initialfile=os.path.basename(out))
            if save:
                shutil.copy2(out, save)
                messagebox.showinfo("Done", f"Saved to:\n{save}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
