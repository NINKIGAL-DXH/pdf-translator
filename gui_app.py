"""
PDF Translator - Alter's Edition
Grid-based GUI (macOS compatible)
"""
import sys, os, threading, shutil
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


class Engine:
    def __init__(self):
        self.config = {'api_url': 'http://127.0.0.1:1234/v1', 'model': 'google/gemma-4-26b-a4b', 'lang_in': 'en', 'lang_out': 'zh'}
        self.state = {'running': False, 'progress': 0, 'status': 'idle', 'error': None, 'output_file': None}
        os.makedirs(os.path.join(BASE_DIR, 'uploads'), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, 'outputs'), exist_ok=True)

    def translate(self, pdf_path, callback=None):
        self.state = {'running': True, 'progress': 0, 'status': 'starting', 'error': None, 'output_file': None}
        job_dir = os.path.join(BASE_DIR, 'outputs', datetime.now().strftime('%Y%m%d_%H%M%S'))
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
                self.state.update(current_page=i+1, total_pages=total, progress=int((i+1)/total*90), status='translating')
                if callback: callback(self.state)
                page_out = os.path.join(job_dir, f'page_{i}')
                os.makedirs(page_out, exist_ok=True)
                result = translate(files=[pdf_path], output=page_out, lang_in=self.config['lang_in'], lang_out=self.config['lang_out'], service='openailiked', thread=1, model=model, pages=[i])
                if result:
                    dest = os.path.join(job_dir, f'mono_p{i}.pdf')
                    shutil.copy2(result[0][0], dest)
                    page_files.append(dest)
            self.state.update(status='merging', progress=95)
            if callback: callback(self.state)
            merged = pymupdf.open()
            for i, f in enumerate(page_files):
                if os.path.exists(f):
                    src = pymupdf.open(f)
                    merged.insert_pdf(src, from_page=i, to_page=i)
                    src.close()
            out = os.path.join(job_dir, f'{Path(pdf_path).stem}-translated.pdf')
            merged.save(out)
            merged.close()
            self.state.update(status='done', output_file=out, progress=100)
            if callback: callback(self.state)
            return out
        except Exception as e:
            self.state.update(status='error', error=str(e))
            if callback: callback(self.state)
            return None

    def cancel(self):
        self.state['running'] = False


# Colors
BG = '#0a0a0f'; SUR = '#1a1a2e'; PRI = '#6c5ce7'; ACC = '#fd79a8'
TXT = '#e0e0e0'; DIM = '#888888'; OK = '#00b894'; ERR = '#d63031'; BDR = '#2d2d44'; INP = '#0f0f23'


class App:
    def __init__(self):
        self.engine = Engine()
        self.file = None
        self.root = tk.Tk()
        self.root.title("PDF Translator")
        self.root.geometry("560x640")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        # Main container using grid
        main = tk.Frame(self.root, bg=BG, padx=24, pady=16)
        main.pack(fill='both', expand=True)

        # Row 0: Header
        hdr = tk.Frame(main, bg=BG)
        hdr.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        tk.Label(hdr, text="PDF Translator", font=('Helvetica', 18, 'bold'), bg=BG, fg=PRI).pack(side='left')
        tk.Label(hdr, text="Alter's Edition", font=('Helvetica', 10), bg=BG, fg=DIM).pack(side='left', padx=(10, 0), pady=(5, 0))

        # Row 1: Separator
        tk.Frame(main, bg=BDR, height=1).grid(row=1, column=0, sticky='ew', pady=(0, 12))

        # Row 2: Upload area
        self.upload = tk.Frame(main, bg=SUR, highlightbackground=BDR, highlightthickness=1, height=100)
        self.upload.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        self.upload.grid_propagate(False)
        c = tk.Frame(self.upload, bg=SUR)
        c.place(relx=0.5, rely=0.5, anchor='center')
        tk.Label(c, text="PDF", font=('Helvetica', 24, 'bold'), bg=SUR, fg=PRI).pack()
        tk.Label(c, text="click to select", font=('Helvetica', 10), bg=SUR, fg=DIM).pack()
        self.upload.bind('<Button-1>', lambda e: self.browse())
        c.bind('<Button-1>', lambda e: self.browse())
        for w in c.winfo_children():
            w.bind('<Button-1>', lambda e: self.browse())

        # Row 3: File info (hidden)
        self.finfo = tk.Frame(main, bg=SUR, height=40)
        self.fname = tk.Label(self.finfo, text="", font=('Helvetica', 11, 'bold'), bg=SUR, fg=TXT)
        self.fname.pack(side='left', padx=12)
        self.fsize = tk.Label(self.finfo, text="", font=('Helvetica', 9), bg=SUR, fg=DIM)
        self.fsize.pack(side='left')
        tk.Button(self.finfo, text="X", font=('Helvetica', 10), bg=SUR, fg=ERR, relief='flat', bd=0, command=self.remove).pack(side='right', padx=12)

        # Row 4: Settings panel (always exists, hidden/shown)
        self.spanel = tk.Frame(main, bg=SUR)
        tk.Label(self.spanel, text="Model", font=('Helvetica', 9), bg=SUR, fg=DIM).grid(row=0, column=0, sticky='w', padx=12, pady=(12, 2))
        self.mentry = tk.Entry(self.spanel, font=('Courier', 10), bg=INP, fg=TXT, insertbackground=TXT, relief='flat')
        self.mentry.insert(0, self.engine.config['model'])
        self.mentry.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 4))
        tk.Label(self.spanel, text="API URL", font=('Helvetica', 9), bg=SUR, fg=DIM).grid(row=2, column=0, sticky='w', padx=12, pady=(4, 2))
        self.aentry = tk.Entry(self.spanel, font=('Courier', 10), bg=INP, fg=TXT, insertbackground=TXT, relief='flat')
        self.aentry.insert(0, self.engine.config['api_url'])
        self.aentry.grid(row=3, column=0, sticky='ew', padx=12, pady=(0, 4))
        lf = tk.Frame(self.spanel, bg=SUR)
        lf.grid(row=4, column=0, sticky='w', padx=12, pady=(4, 12))
        tk.Label(lf, text="From:", font=('Helvetica', 9), bg=SUR, fg=DIM).pack(side='left')
        self.lin = ttk.Combobox(lf, values=['en', 'zh', 'ja', 'ko', 'fr', 'de'], width=6, state='readonly')
        self.lin.set('en')
        self.lin.pack(side='left', padx=(4, 16))
        tk.Label(lf, text="To:", font=('Helvetica', 9), bg=SUR, fg=DIM).pack(side='left')
        self.lout = ttk.Combobox(lf, values=['zh', 'en', 'ja', 'ko', 'fr', 'de'], width=6, state='readonly')
        self.lout.set('zh')
        self.lout.pack(side='left', padx=(4, 0))
        self.spanel.columnconfigure(0, weight=1)

        # Row 5: Buttons
        brow = tk.Frame(main, bg=BG)
        brow.grid(row=5, column=0, sticky='ew', pady=(8, 0))
        self.sbtn = tk.Button(brow, text="Settings", font=('Helvetica', 9), bg=SUR, fg=TXT, relief='flat', padx=12, pady=4, command=self.toggle_settings)
        self.sbtn.pack(side='left')

        # Row 6: Translate button
        self.tbtn = tk.Button(main, text="Translate", font=('Helvetica', 14, 'bold'), bg=PRI, fg='white', relief='flat', pady=10, state='disabled', command=self.translate)
        self.tbtn.grid(row=6, column=0, sticky='ew', pady=(12, 0))

        # Row 7: Progress (hidden)
        self.pframe = tk.Frame(main, bg=SUR)
        self.plabel = tk.Label(self.pframe, text="Starting...", font=('Helvetica', 10), bg=SUR, fg=PRI)
        self.plabel.grid(row=0, column=0, sticky='w', padx=12, pady=(12, 4))
        bar_out = tk.Frame(self.pframe, bg=INP, height=10)
        bar_out.grid(row=1, column=0, sticky='ew', padx=12)
        bar_out.grid_propagate(False)
        self.bar = tk.Frame(bar_out, bg=PRI, height=10)
        self.bar.place(x=0, y=0, width=0, relheight=1)
        self.pct = tk.Label(self.pframe, text="0%", font=('Helvetica', 8), bg=SUR, fg=DIM)
        self.pct.grid(row=2, column=0, sticky='e', padx=12)
        tk.Button(self.pframe, text="Cancel", font=('Helvetica', 9), bg=SUR, fg=TXT, relief='flat', padx=8, pady=2, command=self.cancel).grid(row=3, column=0, sticky='w', padx=12, pady=(4, 8))
        self.pframe.columnconfigure(0, weight=1)

        # Row 8: Result (hidden)
        self.rframe = tk.Frame(main, bg=SUR, highlightbackground=OK, highlightthickness=1)
        tk.Label(self.rframe, text="Done!", font=('Helvetica', 16, 'bold'), bg=SUR, fg=OK).pack(pady=(16, 4))
        self.rinfo = tk.Label(self.rframe, text="", font=('Helvetica', 10), bg=SUR, fg=DIM)
        self.rinfo.pack()
        tk.Button(self.rframe, text="Save PDF", font=('Helvetica', 11, 'bold'), bg=ACC, fg='white', relief='flat', padx=20, pady=6, command=self.download).pack(pady=(12, 16))

        # Row 9: Error (hidden)
        self.eframe = tk.Frame(main, bg=SUR, highlightbackground=ERR, highlightthickness=1)
        tk.Label(self.eframe, text="Error", font=('Helvetica', 12, 'bold'), bg=SUR, fg=ERR).pack(anchor='w', padx=12, pady=(12, 4))
        self.emsg = tk.Label(self.eframe, text="", font=('Courier', 9), bg=INP, fg=DIM, wraplength=480, justify='left')
        self.emsg.pack(fill='x', padx=12, pady=(0, 12))

        # Footer
        tk.Label(self.root, text="Made with lightning by Alter", font=('Helvetica', 8), bg=BG, fg=DIM).pack(side='bottom', pady=6)

        self.settings_on = False

    def browse(self):
        f = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not f:
            return
        self.file = f
        self.upload.grid_forget()
        self.fname.config(text=os.path.basename(f))
        self.fsize.config(text=f"{os.path.getsize(f)/1048576:.1f} MB")
        self.finfo.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        self.tbtn.config(state='normal')

    def remove(self):
        self.file = None
        self.finfo.grid_forget()
        self.upload.grid(row=2, column=0, sticky='ew', pady=(0, 8))
        self.tbtn.config(state='disabled')

    def toggle_settings(self):
        if self.settings_on:
            self.spanel.grid_forget()
            self.settings_on = False
        else:
            self.spanel.grid(row=4, column=0, sticky='ew', pady=(4, 0))
            self.settings_on = True

    def translate(self):
        if not self.file:
            return
        self.engine.config['api_url'] = self.aentry.get()
        self.engine.config['model'] = self.mentry.get()
        self.engine.config['lang_in'] = self.lin.get()
        self.engine.config['lang_out'] = self.lout.get()
        self.tbtn.config(state='disabled', text='Translating...')
        self.rframe.grid_forget()
        self.eframe.grid_forget()
        self.bar.place(width=0)
        self.plabel.config(text="Starting...")
        self.pct.config(text="0%")
        self.pframe.grid(row=7, column=0, sticky='ew', pady=(8, 0))
        threading.Thread(target=lambda: self.engine.translate(self.file, callback=self.on_prog), daemon=True).start()

    def on_prog(self, s):
        self.root.after(0, self._refresh, s)

    def _refresh(self, s):
        p = s['progress']
        self.bar.place(width=int(500 * p / 100))
        self.pct.config(text=f"{p}%")
        st = s['status']
        if st == 'translating':
            self.plabel.config(text=f"Page {s.get('current_page',0)}/{s.get('total_pages',0)}")
        elif st == 'merging':
            self.plabel.config(text="Merging...")
        elif st == 'done':
            self.pframe.grid_forget()
            self.rinfo.config(text=f"{s.get('total_pages',0)} pages translated")
            self.rframe.grid(row=7, column=0, sticky='ew', pady=(8, 0))
            self.tbtn.config(state='normal', text='Translate')
        elif st == 'error':
            self.pframe.grid_forget()
            self.emsg.config(text=str(s.get('error',''))[:200])
            self.eframe.grid(row=7, column=0, sticky='ew', pady=(8, 0))
            self.tbtn.config(state='normal', text='Translate')
        elif st == 'cancelled':
            self.pframe.grid_forget()
            self.tbtn.config(state='normal', text='Translate')

    def cancel(self):
        self.engine.cancel()

    def download(self):
        out = self.engine.state.get('output_file')
        if out and os.path.exists(out):
            s = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[("PDF", "*.pdf")], initialfile=os.path.basename(out))
            if s:
                shutil.copy2(out, s)
                messagebox.showinfo("Done", f"Saved:\n{s}")

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().run()
