"""构建 EXE 发行版

使用方式:
    pip install pyinstaller
    python build.py

构建完成后输出到 dist/xiaohongshu-mcp/ 目录。
用户双击 start.exe 即可启动所有服务。
首次运行会自动下载 Chromium 浏览器引擎到 browsers/ 目录。
"""

import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    spec_file = os.path.join(BASE_DIR, "xiaohongshu.spec")
    if not os.path.exists(spec_file):
        print("错误：找不到 xiaohongshu.spec")
        sys.exit(1)

    # 检查 PyInstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("正在安装 PyInstaller...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )

    print("=" * 48)
    print("  开始构建小红书 MCP Server EXE")
    print("=" * 48)

    dist_dir = os.path.join(BASE_DIR, "dist")
    build_dir = os.path.join(BASE_DIR, "build")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            spec_file,
            "--distpath", dist_dir,
            "--workpath", build_dir,
            "--noconfirm",
        ],
        cwd=BASE_DIR,
        check=True,
    )

    output_dir = os.path.join(dist_dir, "xiaohongshu-mcp")
    print()
    print("=" * 48)
    print(f"  构建完成！")
    print(f"  输出目录: {output_dir}")
    print()
    print("  使用方式:")
    print("  1. 双击 start.exe 启动所有服务")
    print("  2. 首次运行会自动下载 Chromium 浏览器")
    print("  3. 浏览器打开 http://127.0.0.1:8080")
    print("=" * 48)


if __name__ == "__main__":
    main()
