#!/bin/bash
# PDF Translator — Alter's Edition
# Mac .app 构建脚本（在 Mac 上运行）

set -e

APP_NAME="PDF Translator"
APP_DIR="$HOME/Desktop/$APP_NAME.app"

echo "=========================================="
echo " 构建 $APP_NAME.app"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3"
    echo "   brew install python3"
    exit 1
fi

# Create .app structure
echo "📁 创建应用结构..."
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"
mkdir -p "$APP_DIR/Contents/Resources/app"
mkdir -p "$APP_DIR/Contents/Resources/app/templates"
mkdir -p "$APP_DIR/Contents/Resources/app/static"
mkdir -p "$APP_DIR/Contents/Resources/app/uploads"
mkdir -p "$APP_DIR/Contents/Resources/app/outputs"

# Install dependencies
echo "📦 安装依赖..."
python3 -m pip install flask pymupdf openai requests tqdm tenacity numpy onnxruntime -q 2>/dev/null || true
python3 -m pip install babeldoc -q 2>/dev/null || true

# Download pdf2zh if needed
if [ ! -d "$HOME/.pdf-translator/pdf2zh" ]; then
    echo "📥 下载 PDFMathTranslate..."
    mkdir -p "$HOME/.pdf-translator"
    cd "$HOME/.pdf-translator"
    curl -sL https://gh.llkk.cc/https://github.com/Byaidu/PDFMathTranslate/archive/refs/heads/main.zip -o pdf2zh.zip
    unzip -q -o pdf2zh.zip
    mv PDFMathTranslate-main/pdf2zh ./
    rm -rf PDFMathTranslate-main pdf2zh.zip
fi

# Copy pdf2zh
cp -r "$HOME/.pdf-translator/pdf2zh" "$APP_DIR/Contents/Resources/app/"

# Create Info.plist
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>PDF Translator</string>
    <key>CFBundleDisplayName</key>
    <string>PDF Translator</string>
    <key>CFBundleIdentifier</key>
    <string>com.alter.pdftranslator</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# Create launcher script
cat > "$APP_DIR/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$DIR/Resources/app"

# Set Python path
export PYTHONPATH="$APP_DIR:$APP_DIR/pdf2zh:$PYTHONPATH"

# Open browser after delay
sleep 3
open http://localhost:5000 &

# Run Flask app
cd "$APP_DIR"
python3 app.py
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# Download app.py and templates
echo "📄 下载应用文件..."
cd "$APP_DIR/Contents/Resources/app"

# Create app.py
cat > app.py << 'APPEOF'
import sys, os, io, json, shutil, threading, time
from datetime import datetime
from pathlib import Path

if sys.platform == 'darwin':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', template_folder='templates')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), 'outputs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CONFIG = {
    'api_url': 'http://127.0.0.1:1234/v1',
    'model': 'google/gemma-4-26b-a4b',
    'lang_in': 'en', 'lang_out': 'zh',
    'reasoning_effort': 'none',
}

translation_state = {
    'running': False, 'progress': 0, 'total_pages': 0,
    'current_page': 0, 'status': 'idle', 'error': None, 'output_file': None,
}

def get_models():
    try:
        import requests
        r = requests.get(f"{CONFIG['api_url']}/models", timeout=5)
        if r.status_code == 200:
            return [m['id'] for m in r.json().get('data', [])]
    except: pass
    return ['google/gemma-4-26b-a4b']

def translate_pdf(pdf_path, output_dir):
    global translation_state
    try:
        os.environ['OPENAILIKED_BASE_URL'] = CONFIG['api_url']
        os.environ['OPENAILIKED_API_KEY'] = 'not-needed'
        os.environ['OPENAILIKED_MODEL'] = CONFIG['model']
        if CONFIG['reasoning_effort']:
            os.environ['OPENAILIKED_REASONING_EFFORT'] = CONFIG['reasoning_effort']
        
        import pymupdf
        from pdf2zh.high_level import translate
        from pdf2zh.doclayout import OnnxModel
        from babeldoc.assets.assets import get_doclayout_onnx_model_path
        
        model = OnnxModel(get_doclayout_onnx_model_path())
        doc = pymupdf.open(pdf_path)
        total = len(doc)
        doc.close()
        translation_state['total_pages'] = total
        translation_state['status'] = 'translating'
        
        page_files = []
        for i in range(total):
            if not translation_state['running']:
                translation_state['status'] = 'cancelled'
                return None
            translation_state['current_page'] = i + 1
            translation_state['progress'] = int((i + 1) / total * 100)
            page_out = os.path.join(output_dir, f'page_{i}')
            os.makedirs(page_out, exist_ok=True)
            result = translate(files=[pdf_path], output=page_out, lang_in=CONFIG['lang_in'],
                lang_out=CONFIG['lang_out'], service='openailiked', thread=1, model=model, pages=[i])
            if result:
                dest = os.path.join(output_dir, f'mono_p{i}.pdf')
                shutil.copy2(result[0][0], dest)
                page_files.append(dest)
        
        translation_state['status'] = 'merging'
        merged = pymupdf.open()
        for i, f in enumerate(page_files):
            if os.path.exists(f):
                src = pymupdf.open(f)
                merged.insert_pdf(src, from_page=i, to_page=i)
                src.close()
        output_path = os.path.join(output_dir, f'{Path(pdf_path).stem}-translated.pdf')
        merged.save(output_path)
        merged.close()
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
    return render_template('index.html', languages={'en':'English','zh':'中文'}, models=get_models())

@app.route('/api/translate', methods=['POST'])
def api_translate():
    global translation_state
    if translation_state['running']:
        return jsonify({'error': 'Translation already in progress'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are supported'}), 400
    CONFIG['model'] = request.form.get('model', CONFIG['model'])
    CONFIG['lang_in'] = request.form.get('lang_in', CONFIG['lang_in'])
    CONFIG['lang_out'] = request.form.get('lang_out', CONFIG['lang_out'])
    CONFIG['reasoning_effort'] = request.form.get('reasoning_effort', CONFIG['reasoning_effort'])
    CONFIG['api_url'] = request.form.get('api_url', CONFIG['api_url'])
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    job_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    job_dir = os.path.join(OUTPUT_FOLDER, job_id)
    os.makedirs(job_dir, exist_ok=True)
    translation_state = {'running': True, 'progress': 0, 'total_pages': 0, 'current_page': 0,
        'status': 'starting', 'error': None, 'output_file': None, 'job_dir': job_dir}
    def run():
        translate_pdf(filepath, job_dir)
        translation_state['running'] = False
    threading.Thread(target=run, daemon=True).start()
    return jsonify({'message': 'Translation started', 'job_id': job_id})

@app.route('/api/status')
def api_status():
    return jsonify(translation_state)

@app.route('/api/download')
def api_download():
    if not translation_state.get('output_file'):
        return jsonify({'error': 'No output file'}), 404
    return send_file(translation_state['output_file'], as_attachment=True)

@app.route('/api/models')
def api_models():
    return jsonify(get_models())

@app.route('/api/config', methods=['GET','POST'])
def api_config():
    if request.method == 'POST':
        for k in request.json:
            if k in CONFIG: CONFIG[k] = request.json[k]
    return jsonify(CONFIG)

@app.route('/api/history')
def api_history():
    history = []
    if os.path.exists(OUTPUT_FOLDER):
        for jid in sorted(os.listdir(OUTPUT_FOLDER), reverse=True):
            jdir = os.path.join(OUTPUT_FOLDER, jid)
            if os.path.isdir(jdir):
                for f in os.listdir(jdir):
                    if f.endswith('-translated.pdf'):
                        history.append({'job_id': jid, 'filename': f,
                            'size_mb': round(os.path.getsize(os.path.join(jdir, f))/1048576, 1), 'time': jid})
    return jsonify(history)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
APPEOF

# Create templates/index.html
mkdir -p templates
curl -sL "https://raw.githubusercontent.com/user/pdf-translator/main/templates/index.html" -o templates/index.html 2>/dev/null || true

# If templates not downloaded, create minimal version
if [ ! -f templates/index.html ]; then
    cat > templates/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>PDF Translator</title>
<style>body{font-family:system-ui;background:#0a0a0f;color:#e0e0e0;padding:40px}h1{color:#6c5ce7}</style>
</head><body><h1>PDF Translator - Alter's Edition</h1><p>Loading...</p></body></html>
HTMLEOF
fi

echo ""
echo "=========================================="
echo " ✅ 构建完成！"
echo "=========================================="
echo ""
echo " 应用位于: $APP_DIR"
echo ""
echo " 双击即可运行，或拖到 Applications 安装"
echo ""

# Ask if user wants to open
read -p " 打开应用？(y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open "$APP_DIR"
fi
