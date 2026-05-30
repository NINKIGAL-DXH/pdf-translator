"""
PDF Translator — Alter's Edition
Windows 上构建 macOS .app + .zip 的打包脚本

用法: python build_mac_zip.py
产出: dist_mac/PDF-Translator-macOS.zip
"""

import os
import sys
import shutil
import zipfile
import stat
from pathlib import Path

# === 配置 ===
APP_NAME = "PDF Translator"
VERSION = "1.0.0"
BUILD_DIR = Path("dist_mac")
APP_DIR = BUILD_DIR / f"{APP_NAME}.app"
ZIP_PATH = BUILD_DIR / f"PDF-Translator-macOS.zip"

# 源文件目录
SRC_DIR = Path(__file__).parent

print("=" * 50)
print(f"  {APP_NAME} — macOS 打包器")
print(f"  Version: {VERSION}")
print("=" * 50)
print()

# ============================================================
# 第一步：清理
# ============================================================
print("[1/6] 清理旧构建...")
if BUILD_DIR.exists():
    shutil.rmtree(BUILD_DIR)
BUILD_DIR.mkdir(parents=True)
print("  已清理")

# ============================================================
# 第二步：创建 .app 结构
# ============================================================
print("[2/6] 创建 .app 结构...")

(CONTENTS := APP_DIR / "Contents").mkdir(parents=True)
(MACOS := CONTENTS / "MacOS").mkdir()
(RESOURCES := CONTENTS / "Resources").mkdir()
(APP := RESOURCES / "app").mkdir()
(APP / "templates").mkdir()
(APP / "static").mkdir()
(APP / "static" / "css").mkdir()
(APP / "static" / "js").mkdir()
(APP / "uploads").mkdir()
(APP / "outputs").mkdir()
(APP / "pdf2zh").mkdir()
(APP / "lib").mkdir()

print("  结构已创建")

# ============================================================
# 第三步：复制应用文件
# ============================================================
print("[3/6] 复制应用文件...")

# app.py
shutil.copy2(SRC_DIR / "app.py", APP / "app.py")
print("  app.py OK")

# main.py
shutil.copy2(SRC_DIR / "main.py", APP / "main.py")
print("  main.py OK")

# templates
templates_src = SRC_DIR / "templates"
if templates_src.exists():
    for f in templates_src.iterdir():
        if f.is_file():
            shutil.copy2(f, APP / "templates" / f.name)
    print("  templates OK")
else:
    # 创建默认 index.html
    print("  templates 不存在，创建默认页面...")
    (APP / "templates" / "index.html").write_text(DEFAULT_INDEX_HTML, encoding="utf-8")

# static
static_src = SRC_DIR / "static"
if static_src.exists():
    for root, dirs, files in os.walk(static_src):
        rel = Path(root).relative_to(static_src)
        dest = APP / "static" / rel
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, dest / f)
    print("  static OK")

# pdf2zh
pdf2zh_src = SRC_DIR / "pdf2zh"
if pdf2zh_src.exists():
    for root, dirs, files in os.walk(pdf2zh_src):
        rel = Path(root).relative_to(pdf2zh_src)
        dest = APP / "pdf2zh" / rel
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(Path(root) / f, dest / f)
    print("  pdf2zh OK（本地）")
else:
    print("  警告: pdf2zh 目录不存在")
    print("  请手动将 pdf2zh 文件夹复制到 dist_mac/PDF Translator.app/Contents/Resources/app/")

print("  应用文件已就绪")

# ============================================================
# 第四步：创建 Info.plist
# ============================================================
print("[4/6] 创建 macOS 元数据...")

info_plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.alter.pdftranslator</string>
    <key>CFBundleVersion</key>
    <string>{VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>{VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>"""

(CONTENTS / "Info.plist").write_text(info_plist, encoding="utf-8")
print("  Info.plist OK")

# ============================================================
# 第五步：创建启动器脚本
# ============================================================

launcher = r"""#!/bin/bash
# PDF Translator 启动器（自包含 — 自动安装依赖）
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$DIR/Resources/app"

export PYTHONPATH="$APP_DIR:$APP_DIR/lib:$APP_DIR/pdf2zh:$PYTHONPATH"
export PYTHONIOENCODING=utf-8

# 检测 Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    osascript -e 'display dialog "需要安装 Python\n\n请先安装 Homebrew:\nbrew install python" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# 检查并自动安装缺失依赖
MISSING=""
for pkg in flask pymupdf openai requests tqdm tenacity numpy onnxruntime babeldoc; do
    import_name="$pkg"
    [ "$pkg" = "pymupdf" ] && import_name="fitz"
    [ "$pkg" = "onnxruntime" ] && import_name="onnxruntime"
    [ "$pkg" = "babeldoc" ] && import_name="babeldoc"
    if ! $PYTHON_CMD -c "import $import_name" 2>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done

if [ -n "$MISSING" ]; then
    osascript -e "display dialog \"首次运行，正在安装依赖...\\n请稍候。\" buttons {\"OK\"} default button \"OK\" giving up after 2" &
    pip3 install $MISSING -q 2>/dev/null
fi

# 检查端口
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    osascript -e 'display dialog "端口 5000 已被占用\n请关闭后重试" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

sleep 3
open http://localhost:5000 &
cd "$APP_DIR"
exec $PYTHON_CMD app.py
"""

launcher_path = MACOS / "launcher"
launcher_path.write_text(launcher, encoding="utf-8")
# 设置可执行权限（zip 里保留）
launcher_path.chmod(launcher_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

print("  launcher OK")

# ============================================================
# 第六步：打包 zip
# ============================================================
print("[5/6] 打包 zip...")

def add_to_zip(zipf, path, arcname):
    """递归添加文件到 zip，保留权限"""
    if path.is_dir():
        for item in path.iterdir():
            add_to_zip(zipf, item, arcname / item.name)
    elif path.is_file():
        info = zipfile.ZipInfo(str(arcname))
        info.compress_type = zipfile.ZIP_DEFLATED
        # 保留可执行权限
        if path.suffix == '' or 'launcher' in path.name:
            info.external_attr = 0o755 << 16  # rwxr-xr-x
        else:
            info.external_attr = 0o644 << 16  # rw-r--r--
        with open(path, 'rb') as f:
            zipf.writestr(info, f.read())

with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
    add_to_zip(zipf, APP_DIR, Path(f"{APP_NAME}.app"))

zip_size = ZIP_PATH.stat().st_size / 1024 / 1024
print(f"  {ZIP_PATH} ({zip_size:.1f} MB)")

# ============================================================
# 完成
# ============================================================
print()
print("[6/6] 完成！")
print()
print("=" * 50)
print(f"  产出: {ZIP_PATH.absolute()}")
print(f"  大小: {zip_size:.1f} MB")
print("=" * 50)
print()
print("  Mac 用户安装方法:")
print("    1. 下载并解压 zip")
print("    2. 将 PDF Translator.app 拖到 Applications")
print("    3. 首次运行需要安装依赖:")
print("       pip3 install flask pymupdf openai requests tqdm tenacity numpy onnxruntime babeldoc")
print("    4. 右键 → 打开（绕过 Gatekeeper）")
print()


# ============================================================
# 默认 index.html（备用）
# ============================================================
DEFAULT_INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Translator — Alter's Edition</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            width: 90%;
            backdrop-filter: blur(20px);
        }
        h1 {
            font-size: 28px;
            background: linear-gradient(135deg, #6c5ce7, #a29bfe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .subtitle { color: #888; margin-bottom: 30px; }
        .upload-area {
            border: 2px dashed rgba(108,92,231,0.4);
            border-radius: 16px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        .upload-area:hover {
            border-color: #6c5ce7;
            background: rgba(108,92,231,0.05);
        }
        .btn {
            background: linear-gradient(135deg, #6c5ce7, #a29bfe);
            color: white;
            border: none;
            padding: 12px 32px;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 20px;
        }
        .btn:hover { opacity: 0.9; }
        .status { margin-top: 20px; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <h1>PDF Translator</h1>
        <p class="subtitle">Alter's Edition · 基于 LLM 的 PDF 翻译工具</p>
        <div class="upload-area" id="dropZone">
            <p style="font-size:48px;margin-bottom:10px">📄</p>
            <p>拖拽 PDF 文件到这里，或点击选择</p>
            <input type="file" id="fileInput" accept=".pdf" style="display:none">
        </div>
        <div id="settings" style="display:none;margin-top:20px">
            <p>API: <input id="apiUrl" value="http://127.0.0.1:1234/v1" style="width:100%;padding:8px;border-radius:8px;border:1px solid #333;background:#111;color:#eee"></p>
            <p style="margin-top:10px">模型: <input id="model" value="google/gemma-4-26b-a4b" style="width:100%;padding:8px;border-radius:8px;border:1px solid #333;background:#111;color:#eee"></p>
        </div>
        <button class="btn" id="translateBtn" style="display:none">开始翻译</button>
        <div class="status" id="status"></div>
    </div>
    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const translateBtn = document.getElementById('translateBtn');
        const status = document.getElementById('status');
        let selectedFile = null;
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = '#6c5ce7'; });
        dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = 'rgba(108,92,231,0.4)'; });
        dropZone.addEventListener('drop', (e) => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); });
        fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
        function handleFile(file) {
            if (!file || !file.name.endsWith('.pdf')) { alert('请选择 PDF 文件'); return; }
            selectedFile = file;
            dropZone.innerHTML = '<p style="font-size:32px;margin-bottom:10px">✅</p><p>' + file.name + '</p>';
            document.getElementById('settings').style.display = 'block';
            translateBtn.style.display = 'inline-block';
        }
        translateBtn.addEventListener('click', async () => {
            if (!selectedFile) return;
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('api_url', document.getElementById('apiUrl').value);
            formData.append('model', document.getElementById('model').value);
            formData.append('lang_in', 'en');
            formData.append('lang_out', 'zh');
            translateBtn.disabled = true;
            status.textContent = '正在翻译...';
            try {
                const res = await fetch('/api/translate', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.error) { status.textContent = '错误: ' + data.error; return; }
                const poll = setInterval(async () => {
                    const s = await (await fetch('/api/status')).json();
                    status.textContent = s.status + ' — ' + s.progress + '%';
                    if (s.status === 'done') {
                        clearInterval(poll);
                        status.innerHTML = '<a href="/api/download" style="color:#6c5ce7">下载翻译结果</a>';
                        translateBtn.disabled = false;
                    } else if (s.status === 'error') {
                        clearInterval(poll);
                        status.textContent = '错误: ' + s.error;
                        translateBtn.disabled = false;
                    }
                }, 1000);
            } catch (e) {
                status.textContent = '连接失败: ' + e.message;
                translateBtn.disabled = false;
            }
        });
    </script>
</body>
</html>"""
