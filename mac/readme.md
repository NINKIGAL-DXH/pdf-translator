# PDF Translator — Alter's Edition (Mac 版) ⚡

## 安装方法

### 方法一：一键安装（推荐）

1. 下载 `install.sh`
2. 打开终端，进入下载目录
3. 运行：
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
4. 按提示完成安装
5. 浏览器会自动打开 http://localhost:5000

### 方法二：手动安装

```bash
# 安装依赖
pip3 install flask pymupdf openai requests tqdm tenacity numpy onnxruntime

# 下载 pdf2zh
curl -sL https://github.com/Byaidu/PDFMathTranslate/archive/refs/heads/main.zip -o pdf2zh.zip
unzip pdf2zh.zip
mv PDFMathTranslate-main/pdf2zh ./

# 运行
python3 app.py
```

## 使用方法

1. 确保 [LM Studio](https://lmstudio.ai/) 已安装并运行
2. 在 LM Studio 中加载模型
3. 浏览器打开 http://localhost:5000
4. 拖放 PDF → 选模型 → 翻译

## 前提条件

- Python 3.11+
- LM Studio（运行在 http://127.0.0.1:1234）

## 常见问题

**Q: 提示 "No module named 'pdf2zh'"**
A: 重新运行 `./install.sh`，确保 pdf2zh 文件夹存在

**Q: 翻译很慢**
A: 在设置中将「推理强度」改为「关闭」

**Q: 浏览器没自动打开**
A: 手动访问 http://localhost:5000

---

Made with ⚡ by Alter
