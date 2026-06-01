"""
PDF Translator — Alter's Edition
基于 PDFMathTranslate 的本地 PDF 翻译工具

用法: python app.py
然后浏览器打开 http://localhost:5050
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

# Fix encoding for Windows
try:
    if sys.stdout and not sys.stdout.closed:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr and not sys.stderr.closed:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except:
    pass

# Determine base path for bundled app
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

# Add paths
for _p in [_BASE, os.path.join(_BASE, 'pdf2zh')]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__,
    static_folder=os.path.join(_BASE, 'static'),
    template_folder=os.path.join(_BASE, 'templates'))

# === Config ===
UPLOAD_FOLDER = os.path.join(_BASE, 'uploads')
OUTPUT_FOLDER = os.path.join(_BASE, 'outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Default settings
CONFIG = {
    'api_url': 'http://127.0.0.1:1234/v1',
    'model': 'google/gemma-4-26b-a4b',
    'lang_in': 'en',
    'lang_out': 'zh',
    'reasoning_effort': 'none',
    'temperature': 0.3,
}

# Translation state
translation_state = {
    'running': False,
    'progress': 0,
    'total_pages': 0,
    'current_page': 0,
    'status': 'idle',
    'error': None,
    'output_file': None,
}

# Available models (will be fetched from LM Studio)
AVAILABLE_MODELS = [
    'google/gemma-4-26b-a4b',
    'qwen3.5-27b-claude-4.6-opus-reasoning-distilled',
]

# Language options
LANGUAGES = {
    'en': 'English',
    'zh': '中文',
    'ja': '日本語',
    'ko': '한국어',
    'fr': 'Français',
    'de': 'Deutsch',
    'es': 'Español',
    'ru': 'Русский',
}


def get_models():
    """Fetch available models from LM Studio."""
    try:
        import requests
        r = requests.get(f"{CONFIG['api_url']}/models", timeout=5)
        if r.status_code == 200:
            models = [m['id'] for m in r.json().get('data', [])]
            if models:
                return models
    except:
        pass
    return AVAILABLE_MODELS


def translate_pdf(pdf_path, output_dir, pages=None):
    """Run translation in background thread."""
    global translation_state
    
    try:
        # Set environment variables
        os.environ['OPENAILIKED_BASE_URL'] = CONFIG['api_url']
        os.environ['OPENAILIKED_API_KEY'] = 'not-needed'
        os.environ['OPENAILIKED_MODEL'] = CONFIG['model']
        if CONFIG['reasoning_effort']:
            os.environ['OPENAILIKED_REASONING_EFFORT'] = CONFIG['reasoning_effort']
        
        # Import after setting env vars
        import pymupdf
        from pdf2zh.high_level import translate
        from pdf2zh.doclayout import OnnxModel, get_doclayout_onnx_model_path
        
        # Load layout model
        model_path = get_doclayout_onnx_model_path()
        model = OnnxModel(model_path)
        
        # Get page count
        doc = pymupdf.open(pdf_path)
        total = len(doc)
        doc.close()
        
        translation_state['total_pages'] = total
        translation_state['status'] = 'translating'
        
        # Translate page by page (0% to 90%)
        page_files = []
        for i in range(total):
            if not translation_state['running']:
                translation_state['status'] = 'cancelled'
                return None
            
            translation_state['current_page'] = i + 1
            translation_state['progress'] = int((i + 1) / total * 90)  # 0-90%
            
            page_out = os.path.join(output_dir, f'page_{i}')
            os.makedirs(page_out, exist_ok=True)
            
            result = translate(
                files=[pdf_path],
                output=page_out,
                lang_in=CONFIG['lang_in'],
                lang_out=CONFIG['lang_out'],
                service='openailiked',
                thread=1,
                model=model,
                pages=[i],
            )
            
            if result:
                mono_path = result[0][0]
                dest = os.path.join(output_dir, f'mono_p{i}.pdf')
                shutil.copy2(mono_path, dest)
                page_files.append(dest)
        
        # Merge (stays at 90%)
        translation_state['status'] = 'merging'
        translation_state['progress'] = 90
        
        merged = pymupdf.open()
        for i, f in enumerate(page_files):
            if os.path.exists(f):
                src = pymupdf.open(f)
                merged.insert_pdf(src, from_page=i, to_page=i)
                src.close()
        
        # Save
        basename = Path(pdf_path).stem
        output_path = os.path.join(output_dir, f'{basename}-translated.pdf')
        merged.save(output_path)
        merged.close()
        
        # Only now show 100%
        translation_state['status'] = 'done'
        translation_state['output_file'] = output_path
        translation_state['progress'] = 100
        
        return output_path
        
    except Exception as e:
        translation_state['status'] = 'error'
        translation_state['error'] = str(e)
        return None


@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES, models=get_models())


@app.route('/api/translate', methods=['POST'])
def api_translate():
    global translation_state
    
    if translation_state['running']:
        return jsonify({'error': 'Translation already in progress'}), 400
    
    # Get file
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400
    
    # Update config from form
    CONFIG['model'] = request.form.get('model', CONFIG['model'])
    CONFIG['lang_in'] = request.form.get('lang_in', CONFIG['lang_in'])
    CONFIG['lang_out'] = request.form.get('lang_out', CONFIG['lang_out'])
    CONFIG['reasoning_effort'] = request.form.get('reasoning_effort', CONFIG['reasoning_effort'])
    CONFIG['api_url'] = request.form.get('api_url', CONFIG['api_url'])
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    # Create output dir for this job
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    job_dir = os.path.join(OUTPUT_FOLDER, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Reset state
    translation_state = {
        'running': True,
        'progress': 0,
        'total_pages': 0,
        'current_page': 0,
        'status': 'starting',
        'error': None,
        'output_file': None,
        'job_dir': job_dir,
    }
    
    # Start translation in background
    def run():
        translate_pdf(filepath, job_dir)
        translation_state['running'] = False
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return jsonify({'message': 'Translation started', 'job_id': job_id})


@app.route('/api/status')
def api_status():
    return jsonify(translation_state)


@app.route('/api/download')
def api_download():
    if not translation_state.get('output_file'):
        return jsonify({'error': 'No output file'}), 404
    
    filepath = translation_state['output_file']
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(filepath, as_attachment=True)


@app.route('/api/models')
def api_models():
    return jsonify(get_models())


@app.route('/api/config', methods=['GET'])
def api_config_get():
    return jsonify(CONFIG)


@app.route('/api/config', methods=['POST'])
def api_config_set():
    data = request.json
    for key in data:
        if key in CONFIG:
            CONFIG[key] = data[key]
    return jsonify({'message': 'Config updated', 'config': CONFIG})


@app.route('/api/history')
def api_history():
    """List previously translated files."""
    history = []
    if os.path.exists(OUTPUT_FOLDER):
        for job_id in sorted(os.listdir(OUTPUT_FOLDER), reverse=True):
            job_dir = os.path.join(OUTPUT_FOLDER, job_id)
            if os.path.isdir(job_dir):
                for f in os.listdir(job_dir):
                    if f.endswith('-translated.pdf'):
                        filepath = os.path.join(job_dir, f)
                        size = os.path.getsize(filepath)
                        history.append({
                            'job_id': job_id,
                            'filename': f,
                            'size_mb': round(size / 1024 / 1024, 1),
                            'time': job_id,
                        })
    return jsonify(history)


if __name__ == '__main__':
    print("=" * 50)
    print("  PDF Translator — Alter's Edition")
    print("  http://localhost:5050")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5050, debug=False)
