"""
自定义 Logger 组件（基于 loguru）
支持组件标识、日志轮转、彩色控制台输出、动态级别调整，
以及针对 MFAA/MXU 客户端的 UI 适配。

控制台输出到 stderr，MAA 框架会自动捕获并显示到 UI 面板。
"""

import html
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger as _loguru
from maa.context import Context

LEVEL_SHORT_NAMES = {
    "INFO": "info",
    "ERROR": "err",
    "WARNING": "warn",
    "DEBUG": "debug",
    "CRITICAL": "critical",
    "SUCCESS": "success",
    "TRACE": "trace",
}

HTML_LEVEL_COLORS = {
    "TRACE": "royalblue",
    "DEBUG": "deepskyblue",
    "INFO": "forestgreen",
    "SUCCESS": "forestgreen",
    "WARNING": "darkorange",
    "ERROR": "crimson",
    "CRITICAL": "firebrick",
}


def _format_level_short(record):
    record["extra"]["level_short"] = LEVEL_SHORT_NAMES.get(
        record["level"].name, record["level"].name.lower()
    )
    return True


class Logger:
    """自定义 Logger 类，支持组件标识、UI 输出和高级日志功能"""

    COLOR_MAP = {
        "black": "#000000",
        "white": "#FFFFFF",
        "red": "#FF0000",
        "green": "#008000",
        "blue": "#0000FF",
        "yellow": "#FFFF00",
        "cyan": "#00FFFF",
        "magenta": "#FF00FF",
        "orange": "#FFA500",
        "purple": "#800080",
        "pink": "#FFC0CB",
        "brown": "#A52A2A",
        "gray": "#808080",
        "grey": "#808080",
    }

    _initialized = False
    _stderr_handler_id = None
    _compressed_old_logs = False
    _retention_days = 5
    _dir_size_limit_mb = 500

    def __init__(self, name: str, context: Context | None = None, log_dir: str = "debug", retention_days: int = 5, dir_size_limit_mb: int = 500):
        self.name = name
        self.context = context
        _project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.log_dir = _project_root / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if not Logger._initialized:
            Logger._retention_days = retention_days
            Logger._dir_size_limit_mb = dir_size_limit_mb

        client_name = os.environ.get("MAA_CLIENT_NAME", "").strip().upper()
        self._is_mfaa = client_name == "MFAAVALONIA"
        self._is_mxu = client_name == "MXU"

        self._logger = _loguru.bind(name=name)

        if not Logger._compressed_old_logs:
            self._compress_old_logs()
            Logger._compressed_old_logs = True

        if not Logger._initialized:
            self._setup_handlers()
            Logger._initialized = True

    def _setup_handlers(self):
        _loguru.remove()

        Logger._stderr_handler_id = _loguru.add(
            sys.stderr,
            format="<level>{extra[level_short]}</level>:<level>{message}</level>",
            colorize=True,
            level="INFO",
            filter=_format_level_short,
        )

        log_file = self.log_dir / "agent.log"
        log_dir = self.log_dir
        retention_days = Logger._retention_days
        dir_size_limit_mb = Logger._dir_size_limit_mb

        def retention_filter(log_files):
            cutoff = datetime.now() - timedelta(days=retention_days)
            for f in log_dir.glob("*.zip"):
                try:
                    if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                        f.unlink()
                except Exception:
                    pass

            active = {"agent.log", "maafw.log", "deploy.log"}
            files = sorted(
                [f for f in log_dir.iterdir() if f.is_file() and f.name not in active],
                key=lambda f: f.stat().st_mtime,
            )
            total = sum(f.stat().st_size for f in files)
            limit_bytes = dir_size_limit_mb * 1024 * 1024
            while total > limit_bytes and files:
                oldest = files.pop(0)
                total -= oldest.stat().st_size
                try:
                    oldest.unlink()
                except Exception:
                    pass

            return [f for f in log_files if datetime.fromtimestamp(f.stat().st_mtime) > cutoff]

        last_rotation_date = datetime.now().date()

        def rotation_func(message, file):
            nonlocal last_rotation_date
            today = datetime.now().date()
            if today != last_rotation_date:
                last_rotation_date = today
                return True
            try:
                if os.path.getsize(str(log_file)) > 100 * 1024 * 1024:
                    return True
            except OSError:
                pass
            return False

        _loguru.add(
            str(log_file),
            rotation=rotation_func,
            retention=retention_filter,
            compression="zip",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[name]}:{function}:{line} | {message}",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )

    def _compress_old_logs(self):
        for log_file in self.log_dir.iterdir():
            if log_file.is_dir():
                continue
            if log_file.suffix == ".zip":
                continue
            if log_file.name in ("agent.log", "maafw.log", "deploy.log"):
                continue
            zip_path = log_file.with_suffix(log_file.suffix + ".zip")
            if zip_path.exists():
                continue
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.write(log_file, log_file.name)
                log_file.unlink()
            except Exception:
                pass

    def _normalize_color(self, color: str) -> str:
        color = color.strip().lower()
        if color in self.COLOR_MAP:
            return self.COLOR_MAP[color]
        if color.startswith("#"):
            return color
        if re.match(r"^[0-9A-Fa-f]{6}$", color):
            return f"#{color}"
        return "#000000"

    def _is_html(self, text: str) -> bool:
        return bool(re.search(r"<[^>]+>", text, re.IGNORECASE))

    def ui(self, text: str, color: str = "black", level: str = "INFO") -> bool:
        if not self.context:
            return False

        if self._is_html(text):
            html_code = text
        else:
            escaped_text = html.escape(text)

            final_color = color
            if color == "black" and level.upper() in HTML_LEVEL_COLORS:
                final_color = HTML_LEVEL_COLORS[level.upper()]
            hex_color = self._normalize_color(final_color)

            if self._is_mfaa:
                short = LEVEL_SHORT_NAMES.get(level.upper(), "info")
                html_code = f'<span style="color:{hex_color};">{short}:{escaped_text}</span>'
            elif self._is_mxu:
                html_code = f'<span style="color:{hex_color};">{escaped_text}</span>'
            else:
                html_code = f'<font color="{hex_color}">{escaped_text}</font>'

        result = self.context.run_task(
            "自定义信息_为了防止重复所以名字长一点",
            {
                "自定义信息_为了防止重复所以名字长一点": {
                    "focus": {
                        "Node.Recognition.Succeeded": html_code,
                    }
                }
            },
        )
        return bool(result)

    def set_console_level(self, level: str):
        if Logger._stderr_handler_id is not None:
            _loguru.remove(Logger._stderr_handler_id)
        Logger._stderr_handler_id = _loguru.add(
            sys.stderr,
            format="<level>{extra[level_short]}</level>:<level>{message}</level>",
            colorize=True,
            level=level.upper(),
            filter=_format_level_short,
        )

    def _log(self, level: str, message: str, *args, **kwargs):
        getattr(self._logger, level)(message, *args, **kwargs)
        self.ui(message, level=level.upper())

    def debug(self, message: str, *args, **kwargs):
        self._log("debug", message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._log("info", message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._log("warning", message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._log("error", message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._log("critical", message, *args, **kwargs)

    def exception(self, message: str, *args, exc_info=True, **kwargs):
        self._logger.opt(exception=exc_info).error(message, *args, **kwargs)
        self.ui(message, level="ERROR")

    def destroy(self):
        if Logger._initialized:
            _loguru.remove()
            Logger._initialized = False
            Logger._stderr_handler_id = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy()

    def __del__(self):
        try:
            if Logger._initialized:
                self.destroy()
        except Exception:
            pass