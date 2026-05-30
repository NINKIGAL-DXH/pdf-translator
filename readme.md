# PDF Translator — Alter's Edition ⚡

基于 [PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) 的本地 PDF 翻译工具。

## ✨ 特点

- 📄 **保留排版** — 公式、表格、图片位置不变
- 🌐 **双语对照** — 原文+译文对照输出
- 🔒 **完全本地** — 无需联网，保护隐私
- ⚡ **多种模型** — 支持 LM Studio 本地模型
- 🎨 **漂亮界面** — 现代暗色主题

## 🚀 快速开始

### 安装

1. 下载 `PDFTranslator-Setup.exe`
2. 双击运行安装程序
3. 按提示完成安装

### 使用

1. 确保 [LM Studio](https://lmstudio.ai/) 已安装并运行
2. 在 LM Studio 中加载一个模型（推荐 gemma-4-26b-a4b）
3. 双击桌面图标启动 PDF Translator
4. 浏览器会自动打开 http://localhost:5000
5. 拖放 PDF 文件，选择模型，点击翻译

## ⚙️ 配置

### LM Studio 设置

- 默认 API 地址：`http://127.0.0.1:1234/v1`
- 推荐模型：`google/gemma-4-26b-a4b`
- 推理强度：建议关闭（速度快）

### 翻译选项

- **源语言** — 原文语言（默认：English）
- **目标语言** — 翻译语言（默认：中文）
- **推理强度** — 关闭最快，高最准但慢

## 📝 注意事项

- 翻译速度取决于模型大小和页面复杂度
- 每页约 2-10 分钟（关闭推理时）
- 公式和表格会保留原样
- 建议先翻一页测试效果

## 🐛 问题反馈

如有问题，请访问：https://github.com/Byaidu/PDFMathTranslate/issues

## 📜 许可协议

AGPL-3.0 — 基于 PDFMathTranslate

---

Made with ⚡ by Alter
