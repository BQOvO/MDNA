import json
import threading
from maa.custom_action import CustomAction
from maa.context import Context

# 全局字典：task_id -> {"triggered": bool, "timer": Timer}
_timeout_data = {}
_data_lock = threading.Lock()


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
        except:
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
        with _data_lock:
            _timeout_data[task_id] = {
                "triggered": False,
                "timer": timer
            }
        timer.start()

        print(f"[TimeoutStart] 任务 {task_id} 计时开始，{duration} 秒后超时")
        return CustomAction.RunResult(success=True)


class TimeoutReset(CustomAction):
    """取消当前任务的计时器，清除超时标志"""

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            task_id = argv.task_detail.task_id
        except AttributeError as e:
            print(f"[TimeoutReset] 获取 task_id 失败: {e}")
            return CustomAction.RunResult(success=False)

        with _data_lock:
            if task_id in _timeout_data:
                _timeout_data[task_id]["timer"].cancel()
                del _timeout_data[task_id]
                print(f"[TimeoutReset] 任务 {task_id} 计时器已取消")
            else:
                print(f"[TimeoutReset] 任务 {task_id} 没有活跃的计时器")
        return CustomAction.RunResult(success=True)


class CheckTimeout(CustomAction):
    """
    检查当前任务是否超时。
    - 未超时：返回 True（执行 next）
    - 超时：返回 False（执行 on_error）
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

            # 超时触发，清除数据（避免重复触发）
            del _timeout_data[task_id]
            print(f"[CheckTimeout] 任务 {task_id} 超时")

        return CustomAction.RunResult(success=False)