import json
import threading
from maa.custom_action import CustomAction
from maa.context import Context

_timer = None
_timer_lock = threading.Lock()
_timeout_next = None
_tasker = None   # 只保存 tasker，不保存 context

class TimeoutStart(CustomAction):
    DEFAULT_TIMEOUT_NODE = "超时处理"

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        global _timer, _timeout_next, _tasker

        # 解析参数（支持纯数字或 JSON）
        param_str = argv.custom_action_param
        duration = None
        timeout_next = None
        try:
            param = json.loads(param_str)
            if isinstance(param, dict):
                duration = param.get("duration")
                timeout_next = param.get("timeout_next")
            else:
                duration = float(param)
        except (json.JSONDecodeError, ValueError, TypeError):
            try:
                duration = float(param_str)
            except ValueError:
                print("[TimeoutStart] 参数解析失败")
                return CustomAction.RunResult(success=False)

        if duration is None:
            print("[TimeoutStart] 缺少 duration 参数")
            return CustomAction.RunResult(success=False)

        if not timeout_next:
            timeout_next = self.DEFAULT_TIMEOUT_NODE

        # 取消之前的计时器
        with _timer_lock:
            if _timer is not None:
                _timer.cancel()
                _timer = None
            _timeout_next = timeout_next
            _tasker = context.tasker   # 保存 tasker，生命周期长

        # 启动新计时器
        def timeout_callback():
            global _timer, _timeout_next, _tasker
            with _timer_lock:
                if _timer is None:
                    return   # 已被取消
                # 取出超时节点和 tasker，释放全局变量，避免重复执行
                task = _timeout_next
                tasker = _tasker
                _timer = None
                _timeout_next = None
                _tasker = None

            # 在子线程中使用 tasker 的异步 API 执行超时节点
            if tasker and task:
                print(f"[TimeoutStart] 超时！执行节点 {task}")
                try:
                    # 方式1：post_task 投递超时节点（异步）
                    job = tasker.post_task(task)
                    # 可选：等待完成，但会阻塞子线程，不推荐
                    # job.wait()
                except Exception as e:
                    print(f"[TimeoutStart] 超时回调异常: {e}")

        timer = threading.Timer(duration, timeout_callback)
        with _timer_lock:
            _timer = timer
        timer.start()

        print(f"[TimeoutStart] 计时开始，{duration} 秒后超时执行 {timeout_next}")
        return CustomAction.RunResult(success=True)


class TimeoutReset(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        global _timer, _timeout_next, _tasker
        with _timer_lock:
            if _timer is not None:
                _timer.cancel()
                _timer = None
                print("[TimeoutReset] 计时器已取消")
            else:
                print("[TimeoutReset] 没有活跃的计时器")
            _timeout_next = None
            _tasker = None
        return CustomAction.RunResult(success=True)