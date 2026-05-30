# PDF Translator — macOS DMG 构建指南

## 快速开始

在 Mac 终端里执行：

```bash
# 1. 进入 mac 目录
cd /path/to/pdf_translator_app/mac

# 2. 给脚本执行权限
chmod +x build_dmg.sh

# 3. 运行构建
./build_dmg.sh
```

构建完成后，DMG 文件在 `~/Desktop/pdf-translator-build/PDF-Translator-Alter-Edition.dmg`

---

## 前置要求

- macOS 10.15+
- Python 3.9+（`python3 --version` 检查）
- pip3（`pip3 --version` 检查）
- 网络连接（下载依赖用）

### 如果没有 Python

```bash
# 安装 Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python
brew install python
```

---

## 构建过程详解

脚本做了以下 7 件事：

1. **检查环境** — 确认 Python 和 pip 可用
2. **清理旧构建** — 删除之前的构建产物
3. **创建 .app 结构** — macOS 标准的应用目录结构
4. **安装依赖** — 创建虚拟环境，安装 flask、pymupdf、openai 等
5. **复制文件** — app.py、templates、static、pdf2zh、Python 库
6. **创建元数据** — Info.plist、启动器脚本
7. **打包 DMG** — 用 hdiutil 压缩成 DMG

---

## 安装和使用

### 安装

1. 双击 `PDF-Translator-Alter-Edition.dmg`
2. 将 `PDF Translator` 拖到 `Applications` 文件夹
3. 在 Launchpad 或 Applications 中打开

### 首次运行

macOS 可能会阻止运行（"无法验证开发者"）：
- 右键 → 打开 → 再次点打开
- 或者：系统设置 → 隐私与安全性 → 仍要打开

### 运行前需要安装依赖

应用本身不包含 Python 运行时，需要系统有 Python 和依赖：

```bash
pip3 install flask pymupdf openai requests tqdm tenacity numpy onnxruntime babeldoc
```

---

## 自定义图标

将 `.icns` 图标文件放在：

```
pdf_translator_app/mac/AppIcon.icns
```

然后修改 `build_dmg.sh` 中的图标复制步骤：

```bash
cp "$SCRIPT_DIR/mac/AppIcon.icns" "$APP_DIR/Contents/Resources/"
```

---

## 常见问题

### Q: "端口 5000 已被占用"
```bash
# 查看谁占用了端口
lsof -i :5000
# 杀掉进程
kill -9 <PID>
```

### Q: "ModuleNotFoundError: flask"
```bash
pip3 install flask
```

### Q: DMG 打开后闪退
检查 Console.app 中的崩溃日志，通常是缺少依赖。

### Q: 如何修改默认 API 地址
编辑 `app.py` 中的 `CONFIG` 字典。

---

## 技术细节

- **不使用 PyInstaller** — 直接用系统 Python + 虚拟环境
- **应用内包含** — app.py、templates、static、pdf2zh、关键 Python 库
- **不包含** — Python 解释器本身（使用系统 Python）
- **DMG 格式** — UDZO（zlib 压缩），只读
- **启动器** — Bash 脚本，设置 PYTHONPATH 后启动 Flask

---

_构建脚本 by Alter ⚡_
