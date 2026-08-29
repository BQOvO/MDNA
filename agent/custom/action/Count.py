import json
import threading
from collections import defaultdict
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.Logger import Logger

_globals = {}   # {task_id: {"count_xxx": int}}
_targets = {}   # {task_id: {"target_xxx": int}}
_reached = {}   # {task_id: {"count_xxx": bool}}
_lock = threading.RLock()


def _build_vars(task_id):
    """构建模板变量。每个计数器生成 {id} 和 {id_target} 两个变量。
    无 target 时 {id_target} = "∞"。
    """
    vars_dict = {}
    with _lock:
        tid_globals = _globals.get(task_id, {})
        for key, val in tid_globals.items():
            if key.startswith("count_"):
                cid = key[6:]
                vars_dict[cid] = val

        tid_targets = _targets.get(task_id, {})
        for key, val in tid_targets.items():
            if key.startswith("target_"):
                cid = key[7:]
                vars_dict[f"{cid}_target"] = val if val > 0 else "∞"

    return vars_dict


class Count(CustomAction):
    """计数器：每次调用 +1。配了 target 达标时 success=True 走 next，否则走 on_error。

    参数：
      字符串: "all"                   → 无限计数
      字典:   {"id":"all","target":10} → 计数到10达标
              {"id":"all","target":10,"auto_reset":false} → 达标后不自动归零
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            cid = param
            target = 0
            auto_reset = True
        elif isinstance(param, dict):
            cid = param.get("id")
            target = param.get("target", 0)
            auto_reset = param.get("auto_reset", True)
        else:
            print("[Count] 参数格式错误，应为字符串或对象")
            return CustomAction.RunResult(success=False)

        if not cid:
            print("[Count] 缺少 id")
            return CustomAction.RunResult(success=False)

        task_id = argv.task_detail.task_id
        count_key = f"count_{cid}"
        target_key = f"target_{cid}"

        with _lock:
            tid_targets = _targets.setdefault(task_id, {})
            if target_key not in tid_targets:
                tid_targets[target_key] = target

            tid_globals = _globals.setdefault(task_id, {})
            tid_reached = _reached.setdefault(task_id, {})

            if auto_reset and tid_reached.get(count_key, False):
                tid_globals[count_key] = 0
                tid_reached[count_key] = False

            total = tid_globals.get(count_key, 0) + 1
            tid_globals[count_key] = total

        reached = (target > 0 and total >= target)
        if reached and auto_reset:
            with _lock:
                _reached.setdefault(task_id, {})[count_key] = True

        return CustomAction.RunResult(success=reached)


class CountReset(CustomAction):
    """重置计数器归零，保留 target 设置。

    参数：
      字符串: "all"
      字典:   {"id":"all"}
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            cid = param
        elif isinstance(param, dict):
            cid = param.get("id")
        else:
            print("[CountReset] 参数格式错误")
            return CustomAction.RunResult(success=False)

        if not cid:
            print("[CountReset] 缺少 id")
            return CustomAction.RunResult(success=False)

        task_id = argv.task_detail.task_id
        count_key = f"count_{cid}"

        with _lock:
            tid_globals = _globals.setdefault(task_id, {})
            tid_globals[count_key] = 0
            tid_reached = _reached.get(task_id, {})
            tid_reached.pop(count_key, None)

        logger = Logger("CountReset", context)
        logger.ui(f"{cid} → 0", color="cyan")

        return CustomAction.RunResult(success=True)


class CountPrint(CustomAction):
    """输出计数器信息到 UI。

    参数：
      字符串: "第{all}次 成功{success} 失败{failed} 目标{all_target}"
      字典:   {"msg":"第{all}次 成功{success} 失败{failed} 目标{all_target}"}

    模板变量：{id} 和 {id_target}（所有已注册的计数器）。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            msg = param
        elif isinstance(param, dict):
            msg = param.get("msg", "")
        else:
            msg = ""

        task_id = argv.task_detail.task_id

        with _lock:
            vars_dict = _build_vars(task_id)

        if msg:
            safe_vars = defaultdict(lambda: 0, vars_dict)
            output = msg.format_map(safe_vars)
        else:
            parts = []
            for key, val in vars_dict.items():
                if not key.endswith("_target"):
                    parts.append(f"{key}: {val}")
            output = " | ".join(parts) if parts else ""

        logger = Logger("CountPrint", context)
        if output:
            print(output)
            logger.ui(output)
        else:
            logger.ui("[CountPrint] 没有可输出的统计信息", color="gray")

        return CustomAction.RunResult(success=True)


class CountCleanup(CustomAction):
    """清理计数器数据。

    参数：
      不传参: {}
      字符串: "all"                     → 清理指定id
      字典:   {"id":"all"}              → 清理指定id
              {"id":"all","keep_target":true} → 仅归零，保留target
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        task_id = argv.task_detail.task_id

        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = {}

        if isinstance(param, str):
            cid = param
            keep_target = False
        elif isinstance(param, dict):
            cid = param.get("id")
            keep_target = param.get("keep_target", False)
        else:
            cid = None
            keep_target = False

        with _lock:
            if cid:
                count_key = f"count_{cid}"
                target_key = f"target_{cid}"
                tid_globals = _globals.get(task_id, {})
                tid_globals.pop(count_key, None)
                if not tid_globals:
                    _globals.pop(task_id, None)
                tid_reached = _reached.get(task_id, {})
                tid_reached.pop(count_key, None)
                if not tid_reached:
                    _reached.pop(task_id, None)
                if not keep_target:
                    tid_targets = _targets.get(task_id, {})
                    tid_targets.pop(target_key, None)
                    if not tid_targets:
                        _targets.pop(task_id, None)
                logger = Logger("CountCleanup", context)
                logger.ui(f"已清理 {cid}", color="gray")
            else:
                tid_globals = _globals.pop(task_id, {})
                glob_count = len(tid_globals)
                _reached.pop(task_id, None)
                if not keep_target:
                    _targets.pop(task_id, None)
                if glob_count > 0:
                    logger = Logger("CountCleanup", context)
                    logger.ui(f"已清理全部 {glob_count} 个计数器", color="gray")

        return CustomAction.RunResult(success=True)