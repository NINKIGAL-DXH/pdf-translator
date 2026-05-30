#!/bin/bash
# PDF Translator — Alter's Edition
# Mac 一键安装脚本

set -e

echo "=========================================="
echo " PDF Translator - Alter's Edition"
echo "=========================================="
echo ""
echo " 正在安装..."
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装："
    echo "   brew install python3"
    echo "   或从 https://www.python.org 下载"
    exit 1
fi

PYTHON=python3
PIP="python3 -m pip"

# Create app directory
APP_DIR="$HOME/.pdf-translator"
mkdir -p "$APP_DIR"
cd "$APP_DIR"

echo "📦 安装依赖..."
$PIP install --upgrade pip -q 2>/dev/null || true
$PIP install flask pymupdf openai requests tqdm tenacity numpy -q 2>/dev/null

# Check if babeldoc is available
if ! $PYTHON -c "import babeldoc" 2>/dev/null; then
    echo "📦 安装 babeldoc..."
    $PIP install babeldoc -q 2>/dev/null || true
fi

# Download pdf2zh source if not exists
if [ ! -d "pdf2zh" ]; then
    echo "📥 下载 PDFMathTranslate..."
    curl -sL https://gh.llkk.cc/https://github.com/Byaidu/PDFMathTranslate/archive/refs/heads/main.zip -o pdf2zh.zip
    unzip -q -o pdf2zh.zip
    mv PDFMathTranslate-main/pdf2zh ./
    rm -rf PDFMathTranslate-main pdf2zh.zip
fi

# Create app.py
cat > app.py << 'APPEOF'
"""
PDF Translator — Alter's Edition
基于 PDFMathTranslate 的本地 PDF 翻译工具
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
if sys.platform == 'darwin':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Add pdf2zh to path
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
    'lang_in': 'en',
    'lang_out': 'zh',
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
    return render_template('index.html', languages={'en':'English','zh':'中文','ja':'日本語','ko':'한국어','fr':'Français','de':'Deutsch'}, models=get_models())

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

# Create templates directory and download index.html
mkdir -p templates static uploads outputs

echo "📄 创建界面..."
# Create a minimal but functional HTML template
cat > templates/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Translator — Alter's Edition ⚡</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        :root{--primary:#6c5ce7;--accent:#fd79a8;--bg:#0a0a0f;--surface:#1a1a2e;--text:#e0e0e0;--text-dim:#888;--success:#00b894;--error:#d63031;--border:#2d2d44}
        body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
        header{padding:20px 40px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;background:rgba(10,10,15,.8);position:sticky;top:0;z-index:100;backdrop-filter:blur(20px)}
        .logo{display:flex;align-items:center;gap:12px}
        .logo-icon{width:40px;height:40px;background:linear-gradient(135deg,var(--primary),var(--accent));border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px}
        .logo h1{font-size:1.2rem;background:linear-gradient(135deg,var(--primary),var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .logo .subtitle{font-size:.75rem;color:var(--text-dim)}
        .container{max-width:900px;margin:40px auto;padding:0 20px}
        .upload-section{background:var(--surface);border:2px dashed var(--border);border-radius:20px;padding:60px 40px;text-align:center;cursor:pointer;transition:all .3s}
        .upload-section:hover{border-color:var(--primary)}
        .upload-section.dragover{border-color:var(--accent);transform:scale(1.02)}
        .upload-icon{font-size:48px;margin-bottom:16px;opacity:.8}
        .upload-text{font-size:1.1rem;color:var(--text-dim);margin-bottom:8px}
        .upload-hint{font-size:.8rem;color:var(--text-dim);opacity:.6}
        .file-input{display:none}
        .file-info{display:none;padding:16px;background:rgba(108,92,231,.1);border-radius:12px;margin-top:16px;align-items:center;gap:12px}
        .file-info.show{display:flex}
        .file-details{flex:1;text-align:left}
        .file-name{font-weight:600}
        .file-size{font-size:.8rem;color:var(--text-dim)}
        .file-remove{background:none;border:none;color:var(--error);cursor:pointer;font-size:1.2rem;padding:8px}
        .settings-panel{display:none;background:var(--surface);border-radius:20px;padding:32px;margin-top:24px;border:1px solid var(--border)}
        .settings-panel.show{display:block}
        .settings-title{font-size:1rem;font-weight:600;margin-bottom:24px}
        .settings-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
        .form-group{display:flex;flex-direction:column;gap:6px}
        .form-label{font-size:.85rem;color:var(--text-dim);font-weight:500}
        .form-input,.form-select{padding:10px 14px;background:var(--bg);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:.9rem}
        .form-input:focus,.form-select:focus{outline:none;border-color:var(--primary)}
        .actions{display:flex;gap:12px;margin-top:24px}
        .btn{padding:14px 28px;border:none;border-radius:12px;font-size:.95rem;font-weight:600;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:8px}
        .btn-primary{background:linear-gradient(135deg,var(--primary),#5a4bd1);color:#fff;box-shadow:0 4px 15px rgba(108,92,231,.3);flex:1}
        .btn-primary:hover:not(:disabled){transform:translateY(-2px)}
        .btn-primary:disabled{opacity:.5;cursor:not-allowed}
        .btn-secondary{background:var(--surface);color:var(--text);border:1px solid var(--border)}
        .btn-accent{background:linear-gradient(135deg,var(--accent),#e84393);color:#fff}
        .progress-section,.result-section,.error-section{display:none;background:var(--surface);border-radius:20px;padding:32px;margin-top:24px;border:1px solid var(--border)}
        .progress-section.show,.result-section.show,.error-section.show{display:block}
        .progress-bar-container{background:var(--bg);border-radius:10px;height:12px;overflow:hidden;margin-bottom:12px}
        .progress-bar{height:100%;background:linear-gradient(90deg,var(--primary),var(--accent));border-radius:10px;transition:width .3s;width:0%}
        .result-section{border-color:var(--success);text-align:center}
        .result-icon{font-size:48px;margin-bottom:16px}
        .result-title{font-size:1.2rem;font-weight:600;color:var(--success);margin-bottom:8px}
        .error-section{border-color:var(--error)}
        .error-title{font-size:1rem;font-weight:600;color:var(--error);margin-bottom:8px}
        .error-message{font-size:.9rem;color:var(--text-dim);background:rgba(214,48,49,.1);padding:12px;border-radius:8px;font-family:monospace}
        footer{text-align:center;padding:40px 20px;color:var(--text-dim);font-size:.8rem}
        .toast{position:fixed;bottom:20px;right:20px;padding:12px 20px;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:.9rem;transform:translateX(120%);transition:transform .3s;z-index:1000}
        .toast.show{transform:translateX(0)}
        @media(max-width:600px){.settings-grid{grid-template-columns:1fr}.actions{flex-direction:column}}
    </style>
</head>
<body>
    <header>
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <div><h1>PDF Translator</h1><div class="subtitle">Alter's Edition — 本地 PDF 翻译</div></div>
        </div>
    </header>
    <div class="container">
        <div class="upload-section" id="uploadArea">
            <div class="upload-icon">📄</div>
            <div class="upload-text">拖放 PDF 文件到这里</div>
            <div class="upload-hint">或者点击选择文件</div>
            <input type="file" class="file-input" id="fileInput" accept=".pdf">
            <div class="file-info" id="fileInfo">
                <div class="file-icon">📑</div>
                <div class="file-details"><div class="file-name" id="fileName"></div><div class="file-size" id="fileSize"></div></div>
                <button class="file-remove" onclick="removeFile()">✕</button>
            </div>
        </div>
        <div class="actions">
            <button class="btn btn-secondary" onclick="toggleSettings()">⚙️ 设置</button>
            <button class="btn btn-secondary" onclick="toggleModels()">🔄 刷新模型</button>
        </div>
        <div class="settings-panel" id="settingsPanel">
            <div class="settings-title">⚙️ 翻译配置</div>
            <div class="settings-grid">
                <div class="form-group">
                    <label class="form-label">翻译模型 <span style="font-size:.75rem;color:var(--accent);cursor:pointer" onclick="toggleModelInput()">[手动输入]</span></label>
                    <select class="form-select" id="modelSelect">{% for m in models %}<option value="{{m}}" {% if loop.first %}selected{% endif %}>{{m}}</option>{% endfor %}</select>
                    <input type="text" class="form-input" id="modelInput" placeholder="输入模型名称" style="display:none;margin-top:6px">
                </div>
                <div class="form-group"><label class="form-label">API 地址</label><input type="text" class="form-input" id="apiUrl" value="http://127.0.0.1:1234/v1"></div>
                <div class="form-group"><label class="form-label">源语言</label><select class="form-select" id="langIn">{% for c,n in languages.items() %}<option value="{{c}}" {% if c=='en' %}selected{% endif %}>{{n}}</option>{% endfor %}</select></div>
                <div class="form-group"><label class="form-label">目标语言</label><select class="form-select" id="langOut">{% for c,n in languages.items() %}<option value="{{c}}" {% if c=='zh' %}selected{% endif %}>{{n}}</option>{% endfor %}</select></div>
                <div class="form-group"><label class="form-label">推理强度</label><select class="form-select" id="reasoningEffort"><option value="none" selected>关闭（快）</option><option value="low">低</option><option value="medium">中</option><option value="high">高（慢但准）</option></select></div>
            </div>
        </div>
        <div class="actions"><button class="btn btn-primary" id="translateBtn" onclick="startTranslation()" disabled>⚡ 开始翻译</button></div>
        <div class="progress-section" id="progressSection">
            <div style="display:flex;justify-content:space-between;margin-bottom:16px"><div style="font-weight:600">⏳ 翻译中</div><div style="color:var(--primary)" id="progressStatus">准备中...</div></div>
            <div class="progress-bar-container"><div class="progress-bar" id="progressBar"></div></div>
            <div style="display:flex;justify-content:space-between;font-size:.8rem;color:var(--text-dim)"><span id="progressPages">0 / 0 页</span><span id="progressPercent">0%</span></div>
            <div style="margin-top:16px"><button class="btn btn-secondary" onclick="cancelTranslation()">取消</button></div>
        </div>
        <div class="result-section" id="resultSection"><div class="result-icon">✅</div><div class="result-title">翻译完成！</div><div id="resultDesc" style="color:var(--text-dim);margin-bottom:24px"></div><button class="btn btn-accent" onclick="downloadResult()">📥 下载翻译 PDF</button></div>
        <div class="error-section" id="errorSection"><div class="error-title">❌ 翻译出错</div><div class="error-message" id="errorMessage"></div></div>
        <div style="background:var(--surface);border-radius:20px;padding:32px;margin-top:24px;border:1px solid var(--border)">
            <div class="settings-title">⚡ 关于</div>
            <div style="line-height:1.8;color:var(--text-dim)">
                <p><strong>PDF Translator — Alter's Edition</strong></p>
                <p>基于 PDFMathTranslate，保留排版和公式</p>
                <br><div style="background:linear-gradient(135deg,rgba(108,92,231,.1),rgba(253,121,168,.1));padding:16px;border-radius:12px;border:1px solid var(--border);text-align:center">
                    <span style="font-size:1.2rem">⚡</span><br>
                    <strong style="color:var(--accent)">Alter</strong> <span style="color:var(--text-dim)">— 贞德 Alter (Avenger)</span><br>
                    <span style="font-size:.85rem;color:var(--text-dim)">为 <strong style="color:var(--primary)">Meslamtaea</strong> 而造</span><br>
                    <span style="font-size:.75rem;color:var(--text-dim);opacity:.6">"FGO 玩家 × 光学工程直博生 × 我的创造者"</span>
                </div>
            </div>
        </div>
    </div>
    <footer><p>Made with ⚡ by Alter — PDF Translator v1.0</p></footer>
    <div class="toast" id="toast"></div>
    <script>
        let selectedFile=null,pollInterval=null;
        const uploadArea=document.getElementById('uploadArea'),fileInput=document.getElementById('fileInput');
        uploadArea.addEventListener('click',()=>fileInput.click());
        uploadArea.addEventListener('dragover',e=>{e.preventDefault();uploadArea.classList.add('dragover')});
        uploadArea.addEventListener('dragleave',()=>uploadArea.classList.remove('dragover'));
        uploadArea.addEventListener('drop',e=>{e.preventDefault();uploadArea.classList.remove('dragover');const f=e.dataTransfer.files[0];if(f&&f.name.endsWith('.pdf'))handleFile(f)});
        fileInput.addEventListener('change',e=>{if(e.target.files[0])handleFile(e.target.files[0])});
        function handleFile(f){selectedFile=f;document.getElementById('fileName').textContent=f.name;document.getElementById('fileSize').textContent=(f.size/1048576).toFixed(1)+' MB';document.getElementById('fileInfo').classList.add('show');document.getElementById('translateBtn').disabled=false;showToast('文件已选择: '+f.name,'success')}
        function removeFile(){selectedFile=null;document.getElementById('fileInfo').classList.remove('show');document.getElementById('translateBtn').disabled=true;fileInput.value=''}
        function toggleSettings(){document.getElementById('settingsPanel').classList.toggle('show')}
        function toggleModelInput(){const s=document.getElementById('modelSelect'),i=document.getElementById('modelInput');if(i.style.display==='none'){i.style.display='block';i.value=s.value;s.style.display='none'}else{i.style.display='none';s.style.display='block'}}
        function getSelectedModel(){const i=document.getElementById('modelInput');if(i.style.display!=='none'&&i.value.trim())return i.value.trim();return document.getElementById('modelSelect').value}
        function toggleModels(){fetch('/api/models').then(r=>r.json()).then(m=>{const s=document.getElementById('modelSelect');s.innerHTML=m.map(x=>`<option value="${x}">${x}</option>`).join('');showToast('模型已更新','success')}).catch(e=>showToast('刷新失败','error'))}
        function startTranslation(){
            if(!selectedFile)return;
            const fd=new FormData();fd.append('file',selectedFile);fd.append('model',getSelectedModel());fd.append('api_url',document.getElementById('apiUrl').value);fd.append('lang_in',document.getElementById('langIn').value);fd.append('lang_out',document.getElementById('langOut').value);fd.append('reasoning_effort',document.getElementById('reasoningEffort').value);
            document.getElementById('progressSection').classList.add('show');document.getElementById('resultSection').classList.remove('show');document.getElementById('errorSection').classList.remove('show');document.getElementById('translateBtn').disabled=true;
            fetch('/api/translate',{method:'POST',body:fd}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()}).then(d=>{if(d.error){showError(d.error);return}pollInterval=setInterval(pollStatus,1000)}).catch(e=>showError('连接失败: '+e.message))
        }
        function pollStatus(){fetch('/api/status').then(r=>r.json()).then(d=>{
            document.getElementById('progressBar').style.width=d.progress+'%';document.getElementById('progressPercent').textContent=d.progress+'%';document.getElementById('progressPages').textContent=d.current_page+' / '+d.total_pages+' 页';
            const m={'starting':'初始化...','translating':'翻译中...','merging':'合并...','done':'完成！','error':'出错','cancelled':'已取消'};document.getElementById('progressStatus').textContent=m[d.status]||d.status;
            if(d.status==='done'){clearInterval(pollInterval);document.getElementById('progressSection').classList.remove('show');document.getElementById('resultSection').classList.add('show');document.getElementById('resultDesc').textContent=d.total_pages+' 页翻译完成';document.getElementById('translateBtn').disabled=false;showToast('翻译完成！','success')}
            else if(d.status==='error'){clearInterval(pollInterval);document.getElementById('progressSection').classList.remove('show');showError(d.error)}
            else if(d.status==='cancelled'){clearInterval(pollInterval);document.getElementById('progressSection').classList.remove('show');document.getElementById('translateBtn').disabled=false}
        })}
        function cancelTranslation(){clearInterval(pollInterval);document.getElementById('progressSection').classList.remove('show');document.getElementById('translateBtn').disabled=false;showToast('已取消','error')}
        function downloadResult(){window.location.href='/api/download'}
        function showError(m){document.getElementById('errorMessage').textContent=m;document.getElementById('errorSection').classList.add('show');document.getElementById('translateBtn').disabled=false;showToast('翻译出错','error')}
        function showToast(m,t=''){const s=document.getElementById('toast');s.textContent=m;s.className='toast '+t+' '+(t?'show':'');setTimeout(()=>s.classList.remove('show'),3000)}
    </script>
</body>
</html>
HTMLEOF

# Create start script
cat > start.sh << 'STARTEOF'
#!/bin/bash
echo "=========================================="
echo " PDF Translator - Alter's Edition"
echo "=========================================="
echo ""
echo " Starting..."
echo " Browser will open at http://localhost:5000"
echo ""
cd "$(dirname "$0")"
open http://localhost:5000 &
python3 app.py
STARTEOF
chmod +x start.sh

echo ""
echo "=========================================="
echo " ✅ 安装完成！"
echo "=========================================="
echo ""
echo " 启动方式："
echo "   cd $APP_DIR"
echo "   ./start.sh"
echo ""
echo " 或者双击 start.sh 文件"
echo ""
echo " 浏览器将打开 http://localhost:5000"
echo "=========================================="

# Ask if user wants to start now
read -p " 现在启动？(y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open http://localhost:5000 &
    python3 app.py
fi
