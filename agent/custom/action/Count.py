import json
import threading
from maa.custom_action import CustomAction
from maa.context import Context

_globals = {}       # 存储 (task_id, f"count_{id}") -> total
_targets = {}       # 存储 (task_id, f"target_{id}") -> target_total
_lock = threading.Lock()


class Count(CustomAction):
    """
    计数器：根据 id 独立计数，每次调用 +1。
    - 当 target_total > 0 时：达到目标返回成功（触发 next），否则返回失败（触发 onerror）
    - 当 target_total == 0 时：无限计数，永不达标，始终返回失败
    参数:
        id (str): 计数器唯一标识，必填
        target_total (int): 目标次数，0 表示无限计数
        auto_reset (bool): 达标后是否重置计数器，默认 True（无限计数时无效）
        msg (str): 可选消息模板，可用 {id}, {total}, {target}
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except:
            print("[Count] 参数解析失败")
            return CustomAction.RunResult(success=False)

        cid = param.get("id")
        if not cid:
            print("[Count] 缺少 id 参数")
            return CustomAction.RunResult(success=False)

        target_total = param.get("target_total")
        if target_total is None:
            print("[Count] 缺少 target_total 参数")
            return CustomAction.RunResult(success=False)

        task_id = context.task_id
        total_key = (task_id, f"count_{cid}")
        target_key = (task_id, f"target_{cid}")

        with _lock:
            # 存储目标值（首次设置后不再改变）
            if target_key not in _targets:
                _targets[target_key] = target_total
            elif _targets[target_key] != target_total and target_total != 0:
                print(f"[Count] 警告: 计数器 '{cid}' 目标值已存在 ({_targets[target_key]})，忽略新值 {target_total}")

            total = _globals.get(total_key, 0) + 1
            _globals[total_key] = total

        # 输出消息
        msg = param.get("msg")
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

        # 判断是否达标（target_total==0 永远不达标）
        reached = (target_total > 0 and total >= target_total)
        auto_reset = param.get("auto_reset", True)
        if reached and auto_reset:
            with _lock:
                if total_key in _globals:
                    del _globals[total_key]
            print(f"[Count] 计数器 '{cid}' 达标，已重置计数")

        return CustomAction.RunResult(success=reached)


class CountPrint(CustomAction):
    """
    输出指定计数器的当前值（只读）。
    支持三种参数格式：
    1. 列表: ["counter1", "counter2"] 
       输出格式：有目标时 "counter: total/target"，无目标或无限计数时 "counter: total"
    2. 字典: {"counter1": "自定义模板 {total}/{target}", "counter2": None}
       - None 表示使用默认输出
       - 模板中可用 {id}, {total}, {target}（无限计数时 target 显示 "∞"）
    3. 对象: {"ids": [...], "msg": "全局模板"}  —— 兼容旧格式，target 为 None 或无限计数时显示 "∞"
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except:
            print("[CountPrint] 参数解析失败")
            return CustomAction.RunResult(success=False)

        task_id = context.task_id
        with _lock:
            if isinstance(param, list):
                for cid in param:
                    total_key = (task_id, f"count_{cid}")
                    target_key = (task_id, f"target_{cid}")
                    total = _globals.get(total_key, 0)
                    target = _targets.get(target_key)
                    if target is None or target == 0:
                        print(f"{cid}: {total}")
                    else:
                        print(f"{cid}: {total}/{target}")
            elif isinstance(param, dict):
                if "ids" in param or "msg" in param:
                    # 兼容旧对象格式
                    ids = param.get("ids", [])
                    msg_template = param.get("msg")
                    for cid in ids:
                        total_key = (task_id, f"count_{cid}")
                        target_key = (task_id, f"target_{cid}")
                        total = _globals.get(total_key, 0)
                        target = _targets.get(target_key)
                        if msg_template:
                            display_target = "∞" if (target is None or target == 0) else target
                            print(msg_template.format(id=cid, total=total, target=display_target))
                        else:
                            if target is None or target == 0:
                                print(f"{cid}: {total}")
                            else:
                                print(f"{cid}: {total}/{target}")
                else:
                    # 新字典格式
                    for cid, template in param.items():
                        total_key = (task_id, f"count_{cid}")
                        target_key = (task_id, f"target_{cid}")
                        total = _globals.get(total_key, 0)
                        target = _targets.get(target_key)
                        if template is None:
                            if target is None or target == 0:
                                print(f"{cid}: {total}")
                            else:
                                print(f"{cid}: {total}/{target}")
                        else:
                            display_target = "∞" if (target is None or target == 0) else target
                            print(template.format(id=cid, total=total, target=display_target))
            else:
                print("[CountPrint] 参数格式错误，需要列表或字典")
                return CustomAction.RunResult(success=False)

        return CustomAction.RunResult(success=True)