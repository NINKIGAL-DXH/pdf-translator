#!/bin/bash
# ============================================================
# PDF Translator — Alter's Edition
# macOS DMG 构建脚本
# 在 Mac 上运行此脚本即可生成 .dmg 文件
# ============================================================

set -e

APP_NAME="PDF Translator"
DMG_NAME="PDF-Translator-Alter-Edition"
VERSION="1.0.0"
BUILD_DIR="$HOME/Desktop/pdf-translator-build"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
DMG_DIR="$BUILD_DIR/dmg"
DMG_PATH="$BUILD_DIR/$DMG_NAME.dmg"

echo "=========================================="
echo " PDF Translator — DMG 构建器"
echo " Version: $VERSION"
echo "=========================================="
echo ""

# ============================================================
# 第一步：检查环境
# ============================================================
echo "[1/7] 检查环境..."

if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    echo "请先安装: brew install python"
    exit 1
fi

PY_VER=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo "  Python: $PY_VER"

if ! command -v pip3 &> /dev/null; then
    echo "错误: 未找到 pip3"
    exit 1
fi

echo "  环境检查通过"

# ============================================================
# 第二步：清理旧构建
# ============================================================
echo ""
echo "[2/7] 清理旧构建..."

rm -rf "$BUILD_DIR"
rm -rf "$DMG_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$DMG_DIR"

echo "  已清理"

# ============================================================
# 第三步：创建 .app 结构
# ============================================================
echo ""
echo "[3/7] 创建 .app 结构..."

mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"
mkdir -p "$APP_DIR/Contents/Resources/app"
mkdir -p "$APP_DIR/Contents/Resources/app/templates"
mkdir -p "$APP_DIR/Contents/Resources/app/static"
mkdir -p "$APP_DIR/Contents/Resources/app/static/css"
mkdir -p "$APP_DIR/Contents/Resources/app/static/js"
mkdir -p "$APP_DIR/Contents/Resources/app/uploads"
mkdir -p "$APP_DIR/Contents/Resources/app/outputs"
mkdir -p "$APP_DIR/Contents/Resources/app/pdf2zh"

echo "  结构已创建"

# ============================================================
# 第四步：安装 Python 依赖到 app 内部
# ============================================================
echo ""
echo "[4/7] 安装 Python 依赖（可能需要几分钟）..."

# 创建临时虚拟环境
VENV_DIR="$BUILD_DIR/venv"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 安装所有依赖
pip install --upgrade pip -q
pip install \
    flask \
    pymupdf \
    openai \
    requests \
    tqdm \
    tenacity \
    numpy \
    onnxruntime \
    babeldoc \
    -q

echo "  依赖已安装"

# ============================================================
# 第五步：复制应用文件
# ============================================================
echo ""
echo "[5/7] 复制应用文件..."

# 获取当前脚本所在目录（源文件位置）
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# 复制 app.py
cp "$SCRIPT_DIR/app.py" "$APP_DIR/Contents/Resources/app/"

# 复制 main.py
cp "$SCRIPT_DIR/main.py" "$APP_DIR/Contents/Resources/app/"

# 复制 templates
if [ -d "$SCRIPT_DIR/templates" ]; then
    cp -r "$SCRIPT_DIR/templates/"* "$APP_DIR/Contents/Resources/app/templates/"
    echo "  templates 已复制"
else
    echo "  警告: templates 目录不存在，将创建默认页面"
    cat > "$APP_DIR/Contents/Resources/app/templates/index.html" << 'HTMLEOF'
<!DOCTYPE html>
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
</html>
HTMLEOF
fi

# 复制 static
if [ -d "$SCRIPT_DIR/static" ]; then
    cp -r "$SCRIPT_DIR/static/"* "$APP_DIR/Contents/Resources/app/static/"
    echo "  static 已复制"
fi

# 复制 pdf2zh（核心依赖）
if [ -d "$SCRIPT_DIR/pdf2zh" ]; then
    cp -r "$SCRIPT_DIR/pdf2zh/"* "$APP_DIR/Contents/Resources/app/pdf2zh/"
    echo "  pdf2zh 已复制（本地）"
else
    echo "  下载 PDFMathTranslate..."
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    curl -sL https://github.com/Byaidu/PDFMathTranslate/archive/refs/heads/main.zip -o pdf2zh.zip
    unzip -q -o pdf2zh.zip
    cp -r PDFMathTranslate-main/pdf2zh/* "$APP_DIR/Contents/Resources/app/pdf2zh/"
    rm -rf "$TEMP_DIR"
    echo "  pdf2zh 已下载"
fi

# 复制 site-packages 中的关键依赖
echo "  复制 Python 依赖..."
SITE_PACKAGES="$VENV_DIR/lib/python$PY_VER/site-packages"

# 需要打包的关键库
DEPS=(
    "flask" "werkzeug" "jinja2" "markupsafe" "click" "itsdangerous"
    "pymupdf" "fitz"
    "openai" "httpx" "httpcore" "h11" "anyio" "sniffio"
    "requests" "urllib3" "charset_normalizer" "certifi" "idna"
    "numpy" "onnxruntime"
    "tqdm" "tenacity"
    "babeldoc"
    "PIL" "Pillow"
    "cv2"
)

PACKAGES_DIR="$APP_DIR/Contents/Resources/app/lib"
mkdir -p "$PACKAGES_DIR"

for dep in "${DEPS[@]}"; do
    src="$SITE_PACKAGES/$dep"
    if [ -d "$src" ]; then
        cp -r "$src" "$PACKAGES_DIR/"
    elif [ -f "$SITE_PACKAGES/$dep.py" ]; then
        cp "$SITE_PACKAGES/$dep.py" "$PACKAGES_DIR/"
    fi
done

# 复制 .dist-info（可选，用于调试）
# cp -r "$SITE_PACKAGES"/*.dist-info "$PACKAGES_DIR/" 2>/dev/null || true

echo "  应用文件已就绪"

# ============================================================
# 第六步：创建 Info.plist 和启动器
# ============================================================
echo ""
echo "[6/7] 创建 macOS 元数据..."

# Info.plist
cat > "$APP_DIR/Contents/Info.plist" << PLIST
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
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
PLIST

# 启动器脚本
cat > "$APP_DIR/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
# PDF Translator 启动器
DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$DIR/Resources/app"

# 设置 Python 路径
export PYTHONPATH="$APP_DIR:$APP_DIR/lib:$APP_DIR/pdf2zh:$PYTHONPATH"
export PYTHONIOENCODING=utf-8

# 检测系统 Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    osascript -e 'display dialog "需要安装 Python\n\n请先安装 Homebrew，然后运行:\nbrew install python" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# 检查 Flask 是否可用
if ! $PYTHON_CMD -c "import flask" 2>/dev/null; then
    osascript -e 'display dialog "首次运行需要安装依赖，这可能需要几分钟...\n\n请在终端中运行:\npip3 install flask pymupdf openai requests tqdm tenacity numpy onnxruntime babeldoc" buttons {"OK"} default button "OK" with icon caution'
    exit 1
fi

# 检查端口是否被占用
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    osascript -e 'display dialog "端口 5000 已被占用\n\n请关闭占用端口的程序后重试" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# 延迟打开浏览器
sleep 3
open http://localhost:5000 &

# 运行应用
cd "$APP_DIR"
exec $PYTHON_CMD app.py
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# 创建应用图标（使用系统默认图标，后面可以替换）
# 如果有自定义图标，放在 Resources/AppIcon.icns

echo "  元数据已创建"

# ============================================================
# 第七步：打包 DMG
# ============================================================
echo ""
echo "[7/7] 打包 DMG..."

# 将 .app 复制到 DMG 目录
cp -r "$APP_DIR" "$DMG_DIR/"

# 创建 Applications 快捷方式
ln -sf /Applications "$DMG_DIR/Applications"

# 创建 DMG
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo ""
echo "=========================================="
echo " 构建完成！"
echo "=========================================="
echo ""
echo " DMG 文件: $DMG_PATH"
echo " 大小: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo " 安装方法:"
echo "   1. 双击 DMG 文件"
echo "   2. 将 PDF Translator 拖到 Applications"
echo "   3. 在 Launchpad 中打开"
echo ""
echo " 首次运行可能需要:"
echo "   - 安装 Python 依赖: pip3 install flask pymupdf openai ..."
echo "   - 右键 → 打开（绕过 Gatekeeper）"
echo ""

# 询问是否打开
read -p " 打开 DMG 所在目录？(y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open "$BUILD_DIR"
fi

# 清理
deactivate 2>/dev/null || true
rm -rf "$VENV_DIR" 2>/dev/null || true

echo "完成！"
