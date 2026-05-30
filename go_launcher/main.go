// PDF Translator — Alter's Edition
// Go 启动器：自动安装依赖、启动服务、打开浏览器
// 支持 Windows / Mac / Linux 交叉编译

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"
)

func main() {
	fmt.Println("==========================================")
	fmt.Println(" PDF Translator - Alter's Edition")
	fmt.Println("==========================================")
	fmt.Println()

	// Get app directory
	homeDir, _ := os.UserHomeDir()
	appDir := filepath.Join(homeDir, ".pdf-translator")
	os.MkdirAll(appDir, 0755)

	// Check Python
	pythonCmd := findPython()
	if pythonCmd == "" {
		fmt.Println("❌ 未找到 Python3，请先安装：")
		if runtime.GOOS == "darwin" {
			fmt.Println("   brew install python3")
		} else {
			fmt.Println("   从 https://www.python.org 下载")
		}
		waitExit()
		return
	}

	fmt.Printf("✅ Python: %s\n", pythonCmd)
	fmt.Println()

	// Install dependencies
	fmt.Println("📦 检查依赖...")
	installDeps(pythonCmd)

	// Check if app.py exists
	appPy := filepath.Join(appDir, "app.py")
	if _, err := os.Stat(appPy); os.IsNotExist(err) {
		fmt.Println("❌ 未找到应用文件")
		fmt.Println("   请将 app.py 和 templates/ 文件夹复制到：")
		fmt.Printf("   %s\n", appDir)
		waitExit()
		return
	}

	// Start server
	fmt.Println()
	fmt.Println("==========================================")
	fmt.Println(" 启动翻译服务...")
	fmt.Println(" 浏览器将自动打开: http://localhost:5000")
	fmt.Println(" 按 Ctrl+C 停止")
	fmt.Println("==========================================")
	fmt.Println()

	// Open browser after delay
	go func() {
		time.Sleep(3 * time.Second)
		openBrowser("http://localhost:5000")
	}()

	// Run Flask app
	cmd := exec.Command(pythonCmd, appPy)
	cmd.Dir = appDir
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Run()
}

func findPython() string {
	commands := []string{"python3", "python"}
	for _, cmd := range commands {
		if _, err := exec.LookPath(cmd); err == nil {
			out, err := exec.Command(cmd, "--version").Output()
			if err == nil {
				version := string(out)
				if len(version) > 7 && version[7] >= '3' {
					return cmd
				}
			}
		}
	}
	return ""
}

func installDeps(python string) {
	deps := []string{"flask", "pymupdf", "openai", "requests", "tqdm", "tenacity", "numpy", "onnxruntime"}
	for _, dep := range deps {
		exec.Command(python, "-m", "pip", "install", dep, "-q").Run()
	}
	exec.Command(python, "-m", "pip", "install", "babeldoc", "-q").Run()
}

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", url)
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	cmd.Run()
}

func waitExit() {
	fmt.Println()
	fmt.Println("按 Enter 退出...")
	fmt.Scanln()
}
