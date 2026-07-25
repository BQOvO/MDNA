import json
import threading
from maa.custom_action import CustomAction
from maa.context import Context
from ..utils.Logger import Logger

_globals = {}   # {task_id: {"count_xxx": int}}
_targets = {}   # {task_id: {"target_xxx": int}}
_reached = {}   # {task_id: {"count_xxx": bool}}
_lock = threading.RLock()


def _make_format_vars(task_id, current_cid=None):
    """构建模板变量字典。每个计数器生成 {id}_total / {id}_target / {id}_reached 三组变量，
    当前计数器额外提供 {total} {target} {id} {reached} 快捷变量。

    示例：有 all(5/10✓)、failed(2)、success(3) 三个计数器，current_cid="all"
    → {all_total:5, all_target:10, all_reached:"✓",
       failed_total:2, failed_target:"∞", failed_reached:"",
       success_total:3, success_target:"∞", success_reached:"",
       id:"all", total:5, target:10, reached:"✓"}
    """
    vars_dict = {}

    with _lock:
        task_globals = _globals.get(task_id, {})
        for key, val in task_globals.items():
            if key.startswith("count_"):
                cid = key[6:]
                vars_dict[f"{cid}_total"] = val

        task_targets = _targets.get(task_id, {})
        for key, val in task_targets.items():
            if key.startswith("target_"):
                cid = key[7:]
                vars_dict[f"{cid}_target"] = val if val > 0 else "∞"

        task_reached = _reached.get(task_id, {})
        for key, val in task_reached.items():
            if key.startswith("count_"):
                cid = key[6:]
                vars_dict[f"{cid}_reached"] = "✓" if val else ""

    if current_cid:
        vars_dict["id"] = current_cid
        vars_dict["total"] = vars_dict.get(f"{current_cid}_total", 0)
        vars_dict["target"] = vars_dict.get(f"{current_cid}_target", "∞")
        vars_dict["reached"] = vars_dict.get(f"{current_cid}_reached", "")

    return vars_dict


class Count(CustomAction):
    """
    计数器：根据 id 独立计数，每次调用 +1。

    参数：
    - {"id": "xxx", "target_total": 10, "auto_reset": true, "msg": "...", "quiet": false}
    - 字符串：直接作为 id，target_total=0（无限计数）

    模板变量（msg 中可用）：
      快捷变量: {id} {total} {target} {reached}  ← 当前计数器
      全量变量: {xxx_total} {xxx_target} {xxx_reached}  ← 任意计数器
      {reached} / {xxx_reached} = "✓" 或 ""
      {target} / {xxx_target} = 数字 或 "∞"（无限计数）

    无 msg 时：默认格式 "{id}: {total}/{target}" + 达标自动追加 " ✓" + 提示
    有 msg 时：完全由你控制格式，不做任何自动追加

    auto_reset=true（默认）：达标后标记 reached，下次调用自动归零再+1
    auto_reset=false：达标后保持值，需手动 CountReset/CountCleanup
    quiet=true：不输出日志
    success=True 表示达标 → Pipeline 走 next；未达标 → on_error
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            cid = param
            target_total = 0
            auto_reset = True
            msg = None
            quiet = False
        elif isinstance(param, dict):
            cid = param.get("id")
            target_total = param.get("target_total", 0)
            auto_reset = param.get("auto_reset", True)
            msg = param.get("msg")
            quiet = param.get("quiet", False)
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
                tid_targets[target_key] = target_total
            elif tid_targets[target_key] != target_total and target_total != 0:
                if not quiet:
                    print(f"[Count] 警告: '{cid}' 目标值已存在 ({tid_targets[target_key]})，忽略新值 {target_total}")

            tid_globals = _globals.setdefault(task_id, {})
            tid_reached = _reached.setdefault(task_id, {})

            if auto_reset and tid_reached.get(count_key, False):
                tid_globals[count_key] = 0
                tid_reached[count_key] = False

            total = tid_globals.get(count_key, 0) + 1
            tid_globals[count_key] = total

        reached = (target_total > 0 and total >= target_total)
        if reached and auto_reset:
            with _lock:
                _reached.setdefault(task_id, {})[count_key] = True

        if not quiet:
            logger = Logger("Count", context)

            if msg:
                vars_dict = _make_format_vars(task_id, current_cid=cid)
                output = msg.format(**vars_dict)
            else:
                if target_total == 0:
                    output = f"{cid}: {total}"
                else:
                    output = f"{cid}: {total}/{target_total}"

                if reached:
                    output += " ✓"
                    if auto_reset:
                        output += " 下次自动归零"
                    else:
                        output += " 达标"

            if reached:
                logger.ui(output, color="green")
            else:
                logger.ui(output, color="gray")

        return CustomAction.RunResult(success=reached)


class CountReset(CustomAction):
    """
    重置指定计数器（归零），保留 target 设置。
    参数：{"id": "xxx", "quiet": false} 或直接传 id 字符串。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            cid = param
            quiet = False
        elif isinstance(param, dict):
            cid = param.get("id")
            quiet = param.get("quiet", False)
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

        if not quiet:
            logger = Logger("CountReset", context)
            logger.ui(f"{cid} → 0", color="cyan")

        return CustomAction.RunResult(success=True)


class CountPrint(CustomAction):
    """
    输出指定计数器的当前值（只读），合并为一行。

    参数格式：
    - 字符串: "all"                    → "all: 3/10"
    - 列表: ["all","failed","success"] → "all: 3/10 | failed: 2 | success: 3"
    - 字典(逐个): {"all": "模板", "failed": null, "success": "模板"}
    - 字典(统一): {"ids":["all","failed"], "msg":"统一模板", "sep":" | "}
      统一模板可用任意 {id}_total / {id}_target / {id}_reached

    模板变量：
      逐个模式: {id} {total} {target} {reached} + {xxx_total} {xxx_target} {xxx_reached}
      统一模式: {xxx_total} {xxx_target} {xxx_reached}（无快捷变量，用全量名）

    无模板时自动追加 " ✓"；有模板时完全由你控制。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        logger = Logger("CountPrint", context)
        parts = []

        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = argv.custom_action_param

        if isinstance(param, str):
            param = [param]

        task_id = argv.task_detail.task_id

        def _format_one(cid, template=None):
            tid_globals = _globals.get(task_id, {})
            tid_targets = _targets.get(task_id, {})
            tid_reached = _reached.get(task_id, {})
            total = tid_globals.get(f"count_{cid}", 0)
            target = tid_targets.get(f"target_{cid}")
            is_reached = tid_reached.get(f"count_{cid}", False)
            display_target = "∞" if (target is None or target == 0) else target

            if template:
                vars_dict = _make_format_vars(task_id, current_cid=cid)
                text = template.format(**vars_dict)
            elif target is None or target == 0:
                text = f"{cid}: {total}"
            else:
                text = f"{cid}: {total}/{target}"

            if not template and is_reached:
                text += " ✓"
            return text

        with _lock:
            if isinstance(param, list):
                for cid in param:
                    parts.append(_format_one(cid))
            elif isinstance(param, dict):
                if "ids" in param or "msg" in param:
                    ids = param.get("ids", [])
                    msg_template = param.get("msg")
                    if msg_template:
                        vars_dict = _make_format_vars(task_id)
                        parts.append(msg_template.format(**vars_dict))
                    else:
                        for cid in ids:
                            parts.append(_format_one(cid))
                else:
                    for cid, template in param.items():
                        if cid in ("sep", "quiet"):
                            continue
                        parts.append(_format_one(cid, template if template else None))
            else:
                parts.append("[CountPrint] 参数格式错误")

        sep = param.get("sep", " | ") if isinstance(param, dict) else " | "

        if parts:
            logger.ui(sep.join(parts))
        else:
            logger.ui("[CountPrint] 没有可输出的统计信息", color="gray")

        return CustomAction.RunResult(success=True)


class CountCleanup(CustomAction):
    """
    清理计数器数据。
    参数：
    - 不传参：清理当前 task_id 下所有计数器（含 target）
    - {"id": "xxx"}：仅清理指定 id（含 target）
    - {"id": "xxx", "keep_target": true}：仅归零计数+清除标记，保留 target
    - {"quiet": true}：不输出日志
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        task_id = argv.task_detail.task_id

        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            param = {}

        cid = param.get("id") if isinstance(param, dict) else None
        keep_target = param.get("keep_target", False) if isinstance(param, dict) else False
        quiet = param.get("quiet", False) if isinstance(param, dict) else False

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
                if not quiet:
                    logger = Logger("CountCleanup", context)
                    logger.ui(f"已清理 {cid}", color="gray")
            else:
                tid_globals = _globals.pop(task_id, {})
                glob_count = len(tid_globals)
                _reached.pop(task_id, None)
                if not keep_target:
                    _targets.pop(task_id, None)
                if not quiet and glob_count > 0:
                    logger = Logger("CountCleanup", context)
                    logger.ui(f"已清理全部 {glob_count} 个计数器", color="gray")

        return CustomAction.RunResult(success=True)