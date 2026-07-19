"""
自定义 Logger 组件（增强版）
支持组件标识、日志轮转、彩色控制台输出、动态级别调整，
以及针对 MFAA/MXU 客户端的 UI 适配。
"""

import html
import logging
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from maa.context import Context

# ANSI 颜色代码（控制台）
ANSI_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "SUCCESS": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[41m\033[37m",
}
RESET = "\033[0m"

# 级别短名（MFAA 风格）
LEVEL_SHORT_NAMES = {
    "INFO": "info",
    "ERROR": "err",
    "WARNING": "warn",
    "DEBUG": "debug",
    "CRITICAL": "critical",
    "SUCCESS": "success",
    "TRACE": "trace",
}

# UI 默认颜色（MXU 风格）
HTML_LEVEL_COLORS = {
    "TRACE": "royalblue",
    "DEBUG": "deepskyblue",
    "INFO": "forestgreen",
    "SUCCESS": "forestgreen",
    "WARNING": "darkorange",
    "ERROR": "crimson",
    "CRITICAL": "firebrick",
}


class Logger:
    """自定义 Logger 类，支持组件标识、UI 输出和高级日志功能"""

    # 颜色名称到16进制的映射（保留原样）
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

    _handlers_initialized = False  # 全局处理器只初始化一次

    def __init__(self, name: str, context: Context | None = None, log_dir: str = "debug"):
        """
        初始化 Logger

        Args:
            name: 组件名称
            context: MAA Context（可选，用于 UI 输出）
            log_dir: 日志目录（默认 "debug"）
        """
        self.name = name
        self.context = context
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 检测客户端类型
        client_name = os.environ.get("MAA_CLIENT_NAME", "").strip().upper()
        self._is_mfaa = client_name == "MFAAVALONIA"
        self._is_mxu = client_name == "MXU"

        self._logger = logging.getLogger(f"custom.{name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False  # 避免传播到根日志

        # 全局只添加一次 handlers
        if not Logger._handlers_initialized:
            self._setup_handlers()
            Logger._handlers_initialized = True

    def _setup_handlers(self):
        """设置日志处理器：文件轮转 + 彩色控制台"""
        log_file = self.log_dir / "agent.log"

        # 文件处理器（按天轮转，保留 14 天）
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        # 控制台处理器（彩色）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # 默认 INFO
        console_handler.setFormatter(self._ConsoleFormatter())

        # 将处理器添加到 custom 命名空间下的根 logger，避免重复
        root_custom = logging.getLogger("custom")
        root_custom.addHandler(file_handler)
        root_custom.addHandler(console_handler)
        root_custom.setLevel(logging.DEBUG)
        root_custom.propagate = False

    class _ConsoleFormatter(logging.Formatter):
        """控制台彩色格式器，显示组件名和级别颜色"""

        def format(self, record):
            level_name = record.levelname
            color = ANSI_COLORS.get(level_name, "")
            reset = RESET if color else ""
            msg = record.getMessage()
            # 从 logger name 中提取组件名（格式：custom.<component>）
            if record.name.startswith("custom."):
                comp = record.name.split(".", 1)[1]
                msg = f"[{comp}] {msg}"
            return f"{color}{msg}{reset}"

    def _normalize_color(self, color: str) -> str:
        """
        规范化颜色值（保留原功能）

        Args:
            color: 颜色名称或16进制值

        Returns:
            16进制颜色值（带 # 前缀）
        """
        color = color.strip().lower()
        if color in self.COLOR_MAP:
            return self.COLOR_MAP[color]
        if color.startswith("#"):
            return color
        elif re.match(r"^[0-9A-Fa-f]{6}$", color):
            return f"#{color}"
        return "#000000"

    def _is_html(self, text: str) -> bool:
        """检查文本是否已经是 HTML 代码"""
        html_pattern = re.compile(r"<[^>]+>", re.IGNORECASE)
        return bool(html_pattern.search(text))

    def ui(self, text: str, color: str = "black", level: str = "INFO") -> bool:
        """
        生成带颜色的 HTML 代码，并适配不同客户端（MFAA / MXU / 通用）

        Args:
            text: 要显示的文本
            color: 颜色（颜色名称或16进制，如 "red" 或 "#FF0000"）
                  若未指定，将根据 level 自动匹配颜色
            level: 日志级别（用于 MFAA 前缀和默认颜色）

        Returns:
            是否成功注入到 MAA UI
        """
        if not self.context:
            return False

        # 如果文本已经是 HTML，直接传递（不进行额外包装）
        if self._is_html(text):
            html_code = text
        else:
            escaped_text = html.escape(text)

            # 确定最终颜色：优先使用传入的 color，否则根据 level 匹配
            final_color = color
            if color == "black" and level.upper() in HTML_LEVEL_COLORS:
                final_color = HTML_LEVEL_COLORS[level.upper()]
            hex_color = self._normalize_color(final_color)

            # 根据客户端类型构建不同的 HTML 结构
            if self._is_mfaa:
                # MFAA：显示 "级别短名:消息"
                short = LEVEL_SHORT_NAMES.get(level.upper(), "info")
                html_code = f'<span style="color:{hex_color};">{short}:{escaped_text}</span>'
            elif self._is_mxu:
                # MXU：只显示消息，使用 span 着色
                html_code = f'<span style="color:{hex_color};">{escaped_text}</span>'
            else:
                # 通用模式：使用 font 标签（保持原有行为）
                html_code = f'<font color="{hex_color}">{escaped_text}</font>'

        # 通过 MAA Context 注入 UI
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
        """
        动态调整控制台日志级别

        Args:
            level: 日志级别名称（如 "DEBUG", "INFO", "WARNING" 等）
        """
        level_num = getattr(logging, level.upper(), logging.INFO)
        root_custom = logging.getLogger("custom")
        for handler in root_custom.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(level_num)
                break

    # ---------- 标准日志方法 ----------
    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, exc_info=True, **kwargs):
        self._logger.exception(message, *args, exc_info=exc_info, **kwargs)

    # ---------- 资源管理 ----------
    def destroy(self):
        """
        销毁 Logger，清理所有资源
        应在不再使用 Logger 时调用（若使用上下文管理器则自动调用）
        """
        if Logger._handlers_initialized:
            root_custom = logging.getLogger("custom")
            for handler in root_custom.handlers[:]:
                handler.close()
                root_custom.removeHandler(handler)
            Logger._handlers_initialized = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy()

    def __del__(self):
        try:
            if Logger._handlers_initialized:
                self.destroy()
        except Exception:
            pass  # 析构中不抛出异常