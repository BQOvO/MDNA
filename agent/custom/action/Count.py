import json
import threading
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.Logger import Logger   # 导入 Logger

_globals = {}
_targets = {}
_lock = threading.Lock()


class Count(CustomAction):
    """
    计数器：根据 id 独立计数，每次调用 +1。
    参数支持两种格式：
    - 对象：{"id": "xxx", "target_total": 10, "auto_reset": true, "msg": "..."}
    - 字符串：直接作为 id，target_total 自动设为 0（无限计数）
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except:
            param = argv.custom_action_param

        if isinstance(param, str):
            cid = param
            target_total = 0
            auto_reset = True
            msg = None
        elif isinstance(param, dict):
            cid = param.get("id")
            target_total = param.get("target_total")
            auto_reset = param.get("auto_reset", True)
            msg = param.get("msg")
        else:
            print("[Count] 参数格式错误，应为字符串或对象")
            return CustomAction.RunResult(success=False)

        if not cid:
            print("[Count] 缺少 id")
            return CustomAction.RunResult(success=False)

        if target_total is None:
            print("[Count] 缺少 target_total 参数")
            return CustomAction.RunResult(success=False)

        # 正确获取 task_id
        task_id = argv.task_detail.task_id
        total_key = (task_id, f"count_{cid}")
        target_key = (task_id, f"target_{cid}")

        with _lock:
            if target_key not in _targets:
                _targets[target_key] = target_total
            elif _targets[target_key] != target_total and target_total != 0:
                print(f"[Count] 警告: 计数器 '{cid}' 目标值已存在 ({_targets[target_key]})，忽略新值 {target_total}")

            total = _globals.get(total_key, 0) + 1
            _globals[total_key] = total

        if msg:
            if target_total == 0:
                print(msg.format(id=cid, total=total, target="∞"))
            else:
                print(msg.format(id=cid, total=total, target=target_total))
        else:
            if target_total == 0:
                print(f"[Count] 计数器 '{cid}' = {total} (无限计数)")
            else:
                print(f"[Count] 计数器 '{cid}' = {total}/{target_total}")

        reached = (target_total > 0 and total >= target_total)
        if reached and auto_reset:
            with _lock:
                if total_key in _globals:
                    del _globals[total_key]
            print(f"[Count] 计数器 '{cid}' 达标，已重置计数")

        return CustomAction.RunResult(success=reached)


class CountPrint(CustomAction):
    """
    输出指定计数器的当前值（只读），所有信息合并为一行。
    参数支持：
    - 列表: ["id1", "id2"]
    - 字典: {"id1": "模板", "id2": None}
    - 字符串: 单个 id（等同于列表）
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = Logger("CountPrint", context)
        parts = []   # 收集所有输出片段

        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except:
            param = argv.custom_action_param

        if isinstance(param, str):
            param = [param]

        task_id = argv.task_detail.task_id
        with _lock:
            if isinstance(param, list):
                for cid in param:
                    total_key = (task_id, f"count_{cid}")
                    target_key = (task_id, f"target_{cid}")
                    total = _globals.get(total_key, 0)
                    target = _targets.get(target_key)
                    if target is None or target == 0:
                        parts.append(f"{cid}: {total}")
                    else:
                        parts.append(f"{cid}: {total}/{target}")
            elif isinstance(param, dict):
                if "ids" in param or "msg" in param:
                    ids = param.get("ids", [])
                    msg_template = param.get("msg")
                    for cid in ids:
                        total_key = (task_id, f"count_{cid}")
                        target_key = (task_id, f"target_{cid}")
                        total = _globals.get(total_key, 0)
                        target = _targets.get(target_key)
                        if msg_template:
                            display_target = "∞" if (target is None or target == 0) else target
                            parts.append(msg_template.format(id=cid, total=total, target=display_target))
                        else:
                            if target is None or target == 0:
                                parts.append(f"{cid}: {total}")
                            else:
                                parts.append(f"{cid}: {total}/{target}")
                else:
                    for cid, template in param.items():
                        total_key = (task_id, f"count_{cid}")
                        target_key = (task_id, f"target_{cid}")
                        total = _globals.get(total_key, 0)
                        target = _targets.get(target_key)
                        if template is None:
                            if target is None or target == 0:
                                parts.append(f"{cid}: {total}")
                            else:
                                parts.append(f"{cid}: {total}/{target}")
                        else:
                            display_target = "∞" if (target is None or target == 0) else target
                            parts.append(template.format(id=cid, total=total, target=display_target))
            else:
                parts.append("[CountPrint] 参数格式错误，需要列表、字典或字符串")

        # 合并为一行输出
        if parts:
            logger.ui(" | ".join(parts))
        else:
            logger.ui("[CountPrint] 没有可输出的统计信息", color="gray")

        return CustomAction.RunResult(success=True)