"""任务结束时自动清理 Count 计数器数据，避免内存泄漏。无需修改 pipeline。"""

from maa.agent.agent_server import AgentServer
from maa.event_sink import NotificationType
from maa.tasker import Tasker, TaskerEventSink

from ..action.Count import _globals, _targets, _lock


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
            glob_keys = [k for k in _globals if k[0] == task_id]
            for k in glob_keys:
                del _globals[k]
            target_keys = [k for k in _targets if k[0] == task_id]
            for k in target_keys:
                del _targets[k]

        if glob_keys or target_keys:
            print(f"[CountAutoCleanup] 已清理 task={task_id} 的 {len(glob_keys)} 个计数 / {len(target_keys)} 个目标")