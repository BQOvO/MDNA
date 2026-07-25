"""
节点级截图 Sink，每个识别节点完成时自动截图保存。

截图保存到: debug/screenshots/{年}.{月}.{日}-{时}.{分}.{秒}.{毫秒}_{节点名}_{识别ID}_{failed|success}.jpg
最多保留 300 张，环形覆盖旧图。

使用 ContextEventSink（节点级），每个节点识别后直接拿图保存为 JPG。
"""

import os
import struct
from datetime import datetime
from pathlib import Path

import numpy as np

from maa.agent.agent_server import AgentServer
from maa.context import Context, ContextEventSink
from maa.event_sink import NotificationType

from agent.custom.utils.Logger import Logger

_SCREENSHOT_DIR = os.environ.get(
    "MDNA_DEBUG_DIR",
    str(Path.cwd() / "debug"),
)
_SCREENSHOT_DIR = str(Path(_SCREENSHOT_DIR) / "screenshots")
_MAX_SCREENSHOTS = 300    # 最多保留 300 张截图

_log = Logger("ScreenshotOnFail")
_log.info("ScreenshotOnFail 模块已加载")

_HAS_CV2 = False
try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    _log.warning("cv2 不可用，将回退到 BMP 格式")


def _cleanup_old_screenshots() -> int:
    dirpath = Path(_SCREENSHOT_DIR)
    dirpath.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [f for f in dirpath.glob("*") if f.suffix.lower() in (".jpg", ".bmp")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for f in files[_MAX_SCREENSHOTS:]:
        f.unlink()
        deleted += 1
    return deleted


def _save_image(img: np.ndarray, filepath: Path) -> bool:
    if img is None or img.size == 0:
        return False

    if _HAS_CV2:
        success, encoded = cv2.imencode(
            ".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85]
        )
        if not success:
            return False
        with open(filepath, "wb") as f:
            f.write(encoded.tobytes())
        return True

    return _save_bmp(img, filepath.with_suffix(".bmp"))


def _save_bmp(img: np.ndarray, filepath: Path) -> bool:
    if not img.flags.c_contiguous:
        img = np.ascontiguousarray(img)

    h, w = img.shape[:2]
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    elif img.ndim == 3:
        channels = img.shape[2]
        if channels == 1:
            img = np.stack([img[:, :, 0]] * 3, axis=-1)
        elif channels == 4:
            img = img[:, :, :3]
        elif channels == 2:
            img = np.dstack([img[:, :, :2], np.zeros((h, w), dtype=img.dtype)])
        elif channels != 3:
            return False

    row_size = (w * 3 + 3) // 4 * 4
    pixel_data_size = row_size * h
    file_size = 14 + 40 + pixel_data_size

    with open(filepath, "wb") as f:
        f.write(b"BM")
        f.write(struct.pack("<I", file_size))
        f.write(struct.pack("<HH", 0, 0))
        f.write(struct.pack("<I", 14 + 40))

        f.write(struct.pack("<I", 40))
        f.write(struct.pack("<i", w))
        f.write(struct.pack("<i", h))
        f.write(struct.pack("<H", 1))
        f.write(struct.pack("<H", 24))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", pixel_data_size))
        f.write(struct.pack("<i", 2835))
        f.write(struct.pack("<i", 2835))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", 0))

        padding = b"\x00" * (row_size - w * 3)
        for r in range(h - 1, -1, -1):
            f.write(img[r, :, :3].tobytes())
            if padding:
                f.write(padding)

    return True


@AgentServer.context_sink()
class NodeScreenshotSink(ContextEventSink):
    def on_node_pipeline_node(
        self,
        context: Context,
        noti_type: NotificationType,
        detail: ContextEventSink.NodePipelineNodeDetail,
    ):
        node_name = detail.name or "unknown"

        img: np.ndarray | None = None
        reco_id = 0
        if noti_type in (NotificationType.Succeeded, NotificationType.Failed):
            try:
                node_detail = context.tasker.get_node_detail(detail.node_id)
                if node_detail and node_detail.recognition:
                    reco_id = node_detail.recognition.reco_id
                    reco_detail = context.tasker.get_recognition_detail(reco_id)
                    if reco_detail:
                        img = getattr(reco_detail, "raw_image", None)
            except Exception:
                pass

        if img is None or img.size == 0:
            return

        dirpath = Path(_SCREENSHOT_DIR)
        dirpath.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y.%m.%d-%H.%M.%S.%f")[:-3]
        status = "success" if noti_type == NotificationType.Succeeded else "failed"
        filename = f"{timestamp}_{node_name}_{reco_id}_{status}.jpg"
        filepath = dirpath / filename

        _save_image(img, filepath)
        _cleanup_old_screenshots()