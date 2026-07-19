"""
分辨率检查器

在任务开始时检查模拟器分辨率是否为 16:9，如果不是则停止任务并输出警告。
"""

from maa.agent.agent_server import AgentServer
from maa.event_sink import NotificationType
from maa.tasker import Tasker, TaskerEventSink

from ..utils.Logger import Logger

logger = Logger("AspectRatioChecker")

# 模块加载时输出，确认已加载
logger.info("AspectRatioChecker 模块已加载")

SWITCH_ACCOUNT_REQUIRED_RESOLUTION = (1280, 720)

# 允许常见分辨率四舍五入带来的 1 像素误差，例如 1366x768。
MAX_ASPECT_RATIO_PIXEL_ERROR = 1


def is_aspect_ratio_16x9(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    long_side = max(width, height)
    short_side = min(width, height)
    error = abs(long_side * 9 - short_side * 16)
    return error <= 16 * MAX_ASPECT_RATIO_PIXEL_ERROR


def calculate_aspect_ratio(width: int, height: int) -> float:
    w = float(width)
    h = float(height)
    return w / h if w > h else h / w


def get_controller_resolution(controller, ensure_screencap: bool = True) -> tuple[int, int]:
    if controller is None:
        return (0, 0)
    if ensure_screencap:
        try:
            img = controller.cached_image
            if img is None:
                controller.post_screencap().wait().get()
        except Exception as exc:
            logger.warning(f"初始化分辨率失败: {exc}")
    try:
        width, height = controller.resolution
    except Exception as exc:
        logger.warning(f"获取控制器分辨率失败: {exc}")
        return (0, 0)
    return (int(width), int(height))


def format_resolution(width: int, height: int) -> str:
    return f"{width}x{height}"


@AgentServer.tasker_sink()
class AspectRatioChecker(TaskerEventSink):
    """
    分辨率检查器
    在任务开始时检查设备分辨率是否为 16:9
    """

    def on_tasker_task(
        self,
        tasker: Tasker,
        noti_type: NotificationType,
        detail: TaskerEventSink.TaskerTaskDetail,
    ):
        if noti_type != NotificationType.Starting:
            return

        if detail.entry == "MaaTaskerPostStop":
            logger.info("收到 PostStop 事件，跳过分辨率检查")
            return

        logger.info(
            f"任务开始前检查分辨率 - task_id: {detail.task_id}, entry: {detail.entry}"
        )

        controller = tasker.controller
        if controller is None:
            logger.error("无法获取控制器")
            return

        width, height = get_controller_resolution(controller, ensure_screencap=True)
        if width <= 0 or height <= 0:
            logger.error("无法获取控制器实际未缩放分辨率")
            tasker.post_stop()
            return

        logger.info(f"实际未缩放分辨率: {format_resolution(width, height)}")

        if detail.entry == "SwitchAccount":
            if (width, height) != SWITCH_ACCOUNT_REQUIRED_RESOLUTION:
                logger.error(
                    f"切换账号仅支持 1280x720，当前: {format_resolution(width, height)}"
                )
                tasker.post_stop()
            else:
                logger.info(
                    f"切换账号分辨率检查通过: {format_resolution(width, height)}"
                )
            return

        if not is_aspect_ratio_16x9(width, height):
            actual_ratio = calculate_aspect_ratio(width, height)
            logger.error(
                f"🚨 分辨率比例不匹配！任务已停止。"
                f"当前: {format_resolution(width, height)} (比例: {actual_ratio:.4f})，"
                f"MDNA 仅支持 16:9 比例，请调整为: 2560x1440, 1920x1080, 1600x900, 1280x720(推荐)"
            )
            tasker.post_stop()
        else:
            logger.info(f"分辨率检查通过: {format_resolution(width, height)} (16:9)")