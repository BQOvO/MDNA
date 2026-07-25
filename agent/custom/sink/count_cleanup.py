"""任务结束时自动清理 Count 计数器数据，避免内存泄漏。无需修改 pipeline。"""

from maa.agent.agent_server import AgentServer
from maa.event_sink import NotificationType
from maa.tasker import Tasker, TaskerEventSink

from ..action.Count import _globals, _targets, _reached, _lock


@AgentServer.tasker_sink()
class CountAutoCleanup(TaskerEventSink):
    def on_tasker_task(
        self,
        tasker: Tasker,
        noti_type: NotificationType,
        detail: TaskerEventSink.TaskerTaskDetail,
    ):
        if noti_type not in (
            NotificationType.Starting,
            NotificationType.Succeeded,
            NotificationType.Failed,
        ):
            return

        task_id = detail.task_id
        with _lock:
            g = _globals.pop(task_id, {})
            t = _targets.pop(task_id, {})
            r = _reached.pop(task_id, {})

        total = len(g) + len(t) + len(r)
        if total > 0:
            print(f"[CountAutoCleanup] 已清理 task={task_id} 的 {len(g)} 个计数 / {len(t)} 个目标 / {len(r)} 个标记")