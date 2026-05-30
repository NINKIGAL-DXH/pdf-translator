# 用 GitHub Actions 构建 macOS DMG — 操作指南

## 你需要做的（一次性设置）

### 1. 创建 GitHub 仓库

去 https://github.com/new 创建一个新仓库，比如 `pdf-translator`

### 2. 推送代码

在 `pdf_translator_app` 目录下：

```bash
cd pdf_translator_app
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/你的用户名/pdf-translator.git
git push -u origin main
```

### 3. 自动构建

push 后 GitHub Actions 会自动开始构建。去仓库页面：
- 点 **Actions** 标签
- 看到绿色 ✅ 就是构建成功
- 点进去 → **Artifacts** → 下载 `PDF-Translator-macOS`

### 4. 手动触发

也可以在 Actions 页面点 **Run workflow** 手动触发构建。

---

## 构建完成后

你会得到一个 `PDF-Translator-macOS.dmg` 文件（约 30-50 MB）。

Mac 用户：
1. 双击 DMG
2. 拖拽 PDF Translator 到 Applications
3. 打开运行

---

## 常见问题

### Q: 构建失败了怎么办？
去 Actions 页面，点红色 ❌ 的构建，看日志找错误。

### Q: 需要付费吗？
GitHub Actions 对公开仓库免费，私有仓库每月有 2000 分钟免费额度。

### Q: 怎么更新版本？
改代码 → push → 自动构建新 DMG。

### Q: 怎么自动发布 Release？
打 tag 就行：
```bash
git tag v1.0.0
git push origin v1.0.0
```
会自动创建 Release 并附上 DMG 文件。

---

_这是目前最靠谱的跨平台 macOS 打包方案。_
