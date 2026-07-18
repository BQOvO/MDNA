"""
自定义 Logger 组件
支持组件标识、HTML UI 输出、按日期分割日志文件、自动清理过期日志
"""

import html
import logging
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from maa.context import Context


class Logger:
    """统一日志类，支持控制台、文件（按日期分割）、UI 输出和自动清理"""

    # 颜色名称到16进制的映射
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

    # 默认配置
    LOG_DIR = "debug"
    RETENTION_DAYS = 3
    LOG_FORMAT = "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(
        self,
        name: str,
        context: Context | None = None,
        log_by_date: bool = True,
        log_level: int = logging.DEBUG,
    ):
        """
        初始化 Logger

        Args:
            name: 组件名称（也作为日志文件名的一部分）
            context: MAA Context 对象，用于 UI 输出（可选）
            log_by_date: 是否按日期分割日志文件（默认 True）
            log_level: 日志级别（默认 DEBUG）
        """
        self.name = name
        self.context = context
        self.log_by_date = log_by_date
        self._logger = logging.getLogger(f"custom.{name}")
        self._logger.setLevel(log_level)

        # 避免重复添加 handler
        if not self._logger.handlers:
            self._setup_handlers()
            self._clear_old_logs()

    def _get_log_file_path(self) -> Path:
        """获取日志文件路径（支持按日期分割）"""
        log_dir = Path(__file__).parent.parent.parent / self.LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)

        if self.log_by_date:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"{self.name}_{date_str}.log"
        else:
            filename = f"{self.name}.log"

        return log_dir / filename

    def _setup_handlers(self):
        """设置日志处理器：文件（按日期分割）+ 控制台"""
        log_file = self._get_log_file_path()

        # 创建格式器
        formatter = logging.Formatter(self.LOG_FORMAT, datefmt=self.DATE_FORMAT)

        # 文件处理器（追加模式）
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setLevel(self._logger.level)
        file_handler.setFormatter(formatter)

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self._logger.level)
        console_handler.setFormatter(formatter)

        # 添加处理器
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    def _clear_old_logs(self):
        """删除超过 RETENTION_DAYS 天的旧日志文件（仅当按日期分割时）"""
        if not self.log_by_date:
            return

        log_dir = Path(__file__).parent.parent.parent / self.LOG_DIR
        if not log_dir.exists():
            return

        threshold = datetime.now() - timedelta(days=self.RETENTION_DAYS)
        # 匹配当前 logger 名称开头的日志文件，例如 AspectRatioChecker_20260101.log
        for file in log_dir.glob(f"{self.name}_*.log"):
            try:
                # 提取日期部分：文件名 = {name}_YYYYMMDD.log
                date_part = file.stem.split("_")[-1]
                file_date = datetime.strptime(date_part, "%Y%m%d")
                if file_date < threshold:
                    file.unlink()
                    self._logger.info(f"已删除过期日志文件: {file.name}")
            except (ValueError, IndexError):
                # 如果文件名格式不匹配，忽略
                continue

    def _normalize_color(self, color: str) -> str:
        """规范化颜色值"""
        color = color.strip().lower()
        if color in self.COLOR_MAP:
            return self.COLOR_MAP[color]
        if color.startswith("#"):
            return color
        if re.match(r"^[0-9A-Fa-f]{6}$", color):
            return f"#{color}"
        return "#000000"

    def _is_html(self, text: str) -> bool:
        """检查文本是否已经是 HTML"""
        return bool(re.search(r"<[^>]+>", text, re.IGNORECASE))

    def ui(self, text: str, color: str = "black") -> bool:
        """
        生成带颜色的 HTML 并输出到 MAA UI

        Args:
            text: 要显示的文本
            color: 颜色名称或16进制值

        Returns:
            是否成功
        """
        if not self.context:
            return False

        if self._is_html(text):
            html_code = text
        else:
            hex_color = self._normalize_color(color)
            escaped_text = html.escape(text)
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

    # ----- 标准日志方法 -----
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

    def destroy(self):
        """清理所有处理器"""
        if self._logger is None:
            return
        for handler in self._logger.handlers[:]:
            handler.close()
            self._logger.removeHandler(handler)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy()

    def __del__(self):
        try:
            if hasattr(self, "_logger") and self._logger is not None:
                self.destroy()
        except Exception:
            pass