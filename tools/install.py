from pathlib import Path
import shutil
import sys
import json
import jsonc
import platform
import subprocess
import os
from configure import configure_ocr_model

working_dir = Path(__file__).parent.parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

def _raw_os_and_arch() -> tuple[str, str]:
    if len(sys.argv) >= 4:
        return sys.argv[2].strip(), sys.argv[3].strip()
    sys_map = {"windows": "win", "linux": "linux", "darwin": "osx"}
    raw_os = sys_map.get(platform.system().lower(), platform.system().lower())
    return raw_os, platform.machine().lower()

def normalize_os(raw: str) -> str:
    s = raw.lower().strip()
    if s in ("windows", "win32", "win64", "win"):
        return "win"
    if s == "linux":
        return "linux"
    if s in ("darwin", "macos", "osx", "mac"):
        return "osx"
    if s == "android":
        return "android"
    print(f"Unsupported OS: {raw!r}")
    sys.exit(1)

def normalize_arch(raw: str) -> str:
    s = raw.lower().strip()
    if s in ("amd64", "x86_64", "x64", "x86-64"):
        return "x64"
    if s in ("arm64", "aarch64", "armv8", "armv8-a"):
        return "arm64"
    print(f"Unsupported architecture: {raw!r}")
    sys.exit(1)

_raw_os, _raw_arch = _raw_os_and_arch()
current_system = normalize_os(_raw_os)
current_architecture = normalize_arch(_raw_arch)

def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        print('请先下载 MaaFramework 到 "deps"。')
        sys.exit(1)
    shutil.copytree(
        working_dir / "deps" / "bin",
        install_path / "runtimes" / f"{current_system}-{current_architecture}",
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*",
            "*MaaThriftControlUnit*",
            "*MaaRpc*",
            "*MaaHttp*",
        ),
        dirs_exist_ok=True,
    )
    shutil.copytree(
        working_dir / "deps" / "share" / "MaaAgentBinary",
        install_path / "runtimes" / f"{current_system}-{current_architecture}" / "MaaAgentBinary",
        dirs_exist_ok=True,
    )

def install_resource():
    configure_ocr_model()
    shutil.copytree(
        working_dir / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "interface.json",
        install_path,
    )
    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)
    interface["version"] = version
    interface["title"] = f"二重螺旋小助手 Oᴗoಣ 旅途愉快~| 版本号:{version} | 如果出现了bug,请在群里或github的issue中上传日志"
    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)

def install_chores():
    for file in ["README.md", "LICENSE", "logo.png"]:
        shutil.copy2(
            working_dir / file,
            install_path / file,
        )

def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )
    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)
    os_exec_map = {
        "win": r"./python/python.exe",
        "osx": r"./python/bin/python3",
        "linux": r"python3",
    }
    match current_system:
        case "android":
            interface.pop("agent", None)
        case os_name if os_name in os_exec_map:
            interface["agent"]["child_exec"] = os_exec_map[os_name]
            interface["agent"]["child_args"] = ["-u", r"./agent/main.py"]
            interface["agent"]["embedded"] = True
        case _:
            raise ValueError(f"Unknown OS: {current_system}")
    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)
    shutil.copy2(
        working_dir / "requirements.txt",
        install_path / "requirements.txt",
    )

def install_config():
    src = working_dir / "ci" / "config"
    dst = install_path / "config"
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"✅ 已复制配置: {src} -> {dst}")
    else:
        print("ℹ️ 未找到 ci/config 目录，跳过配置复制。")

def install_open_bat():
    src = working_dir / "Open.bat"
    dst = install_path / "Open.bat"
    if src.exists():
        print("Copying Open.bat to install directory...")
        shutil.copy2(src, dst)
    else:
        print("Warning: Open.bat not found in project root. Skipping.")

def install_tasks():
    src = working_dir / "tasks"
    dst = install_path / "tasks"
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"✅ 已复制 tasks: {src} -> {dst}")
    else:
        print("ℹ️ tasks 目录不存在，跳过")


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    install_open_bat()
    install_config()
    install_tasks()
    # --- 修改开始：注释掉函数调用 ---
    # install_maa_bindings()
    # --- 修改结束 ---
    print(f"Install to {install_path} successfully.")