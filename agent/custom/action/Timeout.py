import json
import threading
import time
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.Logger import Logger

# 全局字典：task_id -> {"triggered": bool, "timer": Timer, "start_time": float}
_timeout_data = {}
_data_lock = threading.Lock()


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes} 分 {secs:.1f} 秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours} 时 {minutes} 分 {secs:.1f} 秒"


def _apply_elapsed_to_focus(context, node_name, elapsed, elapsed_str, prefix="Timeout"):
    """将 {elapsed} / {elapsed_raw} 占位符替换到当前节点 focus 中。
    返回 True=已处理，False=无需处理或失败。"""
    try:
        node_data = context.tasker.resource.get_node_data(node_name)
        if not node_data:
            return False
        if isinstance(node_data, str):
            node_data = json.loads(node_data)
        focus = node_data.get("focus", {})
        if not focus or not any(
            isinstance(v, str) and ("{elapsed" in v) for v in focus.values()
        ):
            return False

        new_focus = {}
        for key, value in focus.items():
            if isinstance(value, str):
                new_focus[key] = value.format(elapsed=elapsed_str, elapsed_raw=elapsed)
            else:
                new_focus[key] = value
        context.override_pipeline({node_name: {"focus": new_focus}})
        print(f"[{prefix}] 已用 override_pipeline 更新节点 {node_name} 的 focus")
        return True
    except Exception as e:
        print(f"[{prefix}] 读取/更新 focus 失败: {e}")
        return False


class TimeoutStart(CustomAction):
    """
    启动一个定时器，超时后设置标志。
    参数：
        duration (float): 超时秒数（必填）
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        param_str = argv.custom_action_param
        duration = None

        # 解析参数（支持纯数字或 JSON）
        try:
            param = json.loads(param_str)
            if isinstance(param, dict):
                duration = param.get("duration")
            else:
                duration = float(param)
        except Exception:
            try:
                duration = float(param_str)
            except ValueError:
                print("[TimeoutStart] 参数解析失败")
                return CustomAction.RunResult(success=False)

        if duration is None:
            print("[TimeoutStart] 缺少 duration")
            return CustomAction.RunResult(success=False)

        # 通过 argv.task_detail 获取 task_id
        try:
            task_id = argv.task_detail.task_id
        except AttributeError as e:
            print(f"[TimeoutStart] 获取 task_id 失败: {e}")
            return CustomAction.RunResult(success=False)

        # 清除该任务之前的计时器（如果有）
        with _data_lock:
            if task_id in _timeout_data:
                _timeout_data[task_id]["timer"].cancel()
                del _timeout_data[task_id]

        # 定义超时回调（子线程执行，仅设置标志）
        def timeout_callback():
            with _data_lock:
                if task_id in _timeout_data:
                    _timeout_data[task_id]["triggered"] = True
                    print(f"[TimeoutStart] 任务 {task_id} 超时标志已设置")

        timer = threading.Timer(duration, timeout_callback)
        start_time = time.time()
        with _data_lock:
            _timeout_data[task_id] = {
                "triggered": False,
                "timer": timer,
                "start_time": start_time
            }
        timer.start()

        print(f"[TimeoutStart] 任务 {task_id} 计时开始，{duration} 秒后超时")
        return CustomAction.RunResult(success=True)


class TimeoutReset(CustomAction):
    """
    取消当前任务的计时器，清除超时标志，输出计时用时。
    优先读取当前节点 focus 中的 {elapsed} / {elapsed_raw} 占位符并替换；
    若 focus 中无占位符，则通过 Logger.ui() 输出默认消息。
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            task_id = argv.task_detail.task_id
        except AttributeError as e:
            print(f"[TimeoutReset] 获取 task_id 失败: {e}")
            return CustomAction.RunResult(success=False)

        elapsed = None
        with _data_lock:
            if task_id in _timeout_data:
                data = _timeout_data[task_id]
                data["timer"].cancel()
                if "start_time" in data:
                    elapsed = time.time() - data["start_time"]
                del _timeout_data[task_id]
                print(f"[TimeoutReset] 任务 {task_id} 计时器已取消")
            else:
                print(f"[TimeoutReset] 任务 {task_id} 没有活跃的计时器")

        if elapsed is not None:
            elapsed_str = _format_elapsed(elapsed)
            node_name = argv.node_name

            if not _apply_elapsed_to_focus(context, node_name, elapsed, elapsed_str, prefix="TimeoutReset"):
                logger = Logger("TimeoutReset", context)
                logger.ui(f"计时结束，用时 {elapsed_str}")

        return CustomAction.RunResult(success=True)


class CheckTimeout(CustomAction):
    """
    检查当前任务是否超时。
    - 未超时：返回 True（执行 next）
    - 超时：返回 False（执行 on_error），同时输出计时用时。
    优先读取当前节点 focus 中的 {elapsed} / {elapsed_raw} 占位符并替换。
    """

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            task_id = argv.task_detail.task_id
        except AttributeError as e:
            print(f"[CheckTimeout] 获取 task_id 失败: {e}")
            return CustomAction.RunResult(success=True)  # 获取失败时默认未超时

        with _data_lock:
            if task_id not in _timeout_data:
                return CustomAction.RunResult(success=True)

            data = _timeout_data[task_id]
            if not data["triggered"]:
                return CustomAction.RunResult(success=True)

            # 超时触发，计算耗时并清除数据
            elapsed = None
            if "start_time" in data:
                elapsed = time.time() - data["start_time"]
            del _timeout_data[task_id]
            print(f"[CheckTimeout] 任务 {task_id} 超时")

        if elapsed is not None:
            elapsed_str = _format_elapsed(elapsed)
            node_name = argv.node_name

            if not _apply_elapsed_to_focus(context, node_name, elapsed, elapsed_str, prefix="CheckTimeout"):
                logger = Logger("CheckTimeout", context)
                logger.ui(f"超时！计时 {elapsed_str}，触发超时处理")

        return CustomAction.RunResult(success=False)