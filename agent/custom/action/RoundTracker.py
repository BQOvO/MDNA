import json
import re
import traceback
from maa.context import Context
from maa.custom_action import CustomAction
from ..utils.Logger import Logger


class RoundTracker(CustomAction):
    _last_values = {}

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[RoundTracker] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        roi = param.get("roi")
        expected = param.get("expected")
        number_regex = param.get("number_regex", "\\d+")
        label = param.get("label", "")

        if not roi:
            print("[RoundTracker] 缺少 roi")
            return CustomAction.RunResult(success=False)
        if not expected:
            print("[RoundTracker] 缺少 expected")
            return CustomAction.RunResult(success=False)

        image = self._screencap(context)
        if image is None:
            return CustomAction.RunResult(success=False)

        text = self._ocr_recognize(context, image, roi, expected)
        if text is None:
            print("[RoundTracker] OCR 未能识别到匹配文字")
            return CustomAction.RunResult(success=False)

        match = re.search(number_regex, text)
        if not match:
            print(f"[RoundTracker] 未能从文字中提取数字: \"{text}\", number_regex=\"{number_regex}\"")
            return CustomAction.RunResult(success=False)

        current_number = match.group()
        task_id = argv.task_detail.task_id
        last = self._last_values.get(task_id)

        logger = Logger("RoundTracker", context)

        if last is None:
            self._last_values.clear()
            self._last_values[task_id] = {"text": text, "number": current_number}
            if label:
                logger.ui(f"{label}: {text}")
            else:
                logger.ui(text)
            print(f"[RoundTracker] 首次识别(基线): {current_number}, 走 on_error 继续轮询")
            return CustomAction.RunResult(success=False)

        if last["number"] == current_number:
            print(f"[RoundTracker] 数值未变化: {current_number}, 跳过输出, 走 on_error 继续轮询")
            return CustomAction.RunResult(success=False)

        self._last_values[task_id] = {"text": text, "number": current_number}
        if label:
            logger.ui(f"{label}: {text}")
        else:
            logger.ui(text)
        print(f"[RoundTracker] 数值变化: {last['number']} → {current_number}, 走 next")
        return CustomAction.RunResult(success=True)

    def _screencap(self, context):
        try:
            image = context.tasker.controller.post_screencap().wait().get()
            if image is None:
                print("[RoundTracker] 截图为空")
            return image
        except Exception as e:
            print(f"[RoundTracker] 截图失败: {e}")
            traceback.print_exc()
            return None

    def _ocr_recognize(self, context, image, roi, pattern):
        entry = "_rt_ocr"
        node = {
            "recognition": "OCR",
            "roi": roi,
            "expected": [pattern],
        }
        pipeline = {entry: node}
        try:
            reco = context.run_recognition(entry, image, pipeline)
            if reco and reco.hit:
                detail = reco.detail
                if detail:
                    if isinstance(detail, list) and len(detail) > 0:
                        return str(detail[0])
                    if isinstance(detail, str):
                        return detail
                    return str(detail)
            return None
        except Exception:
            return None


"""
===== RoundTracker 功能说明 =====

轮次进度追踪器：OCR 识别 ROI 中的文字（如 "已完成轮次：x"），提取数字部分，
与上一次识别结果对比。用于轮询检测游戏自动进轮次（6秒过渡后轮次数字+1）。

典型场景：游戏自动进轮次，每轮结束→6秒过渡→轮次数字+1→继续战斗。
RoundTracker 在 pipeline 轮询循环中持续检测，数字变化时走 next 触发后续处理，不变时走 on_error 继续等待。

===== 核心实现 =====

1. OCR 识别：在 ROI 区域内 OCR 匹配 expected 正则，提取识别到的文字。
2. 数字提取：用 number_regex 从文字中提取数字部分（如 "已完成轮次：5" → "5"）。
3. 状态追踪：类级别 _last_values 字典按 task_id 隔离，记录上一次的文字和数字。
4. 变化检测：
   - 首次识别 → 输出 UI，记录基线，走 on_error（继续轮询）
   - 数字相同 → 跳过 UI，走 on_error（还在同一轮，继续等待）
   - 数字变化 → 输出 UI，更新基线，走 next（新轮次来了！）
   - 识别失败 → 走 on_error

===== 使用教程 =====

参数格式：
{
    "roi": [x, y, w, h],          // OCR 识别区域（必填）
    "expected": "已完成轮次：\\\\d+", // OCR 匹配正则（必填，JSON 中需双反斜杠）
    "number_regex": "\\\\d+",       // 数字提取正则（可选，默认 "\\d+"）
    "label": "当前进度"             // UI 输出前缀（可选，默认直接输出文字）
}

===== Pipeline JSON 示例 =====

{
    "检测轮次变化": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "RoundTracker",
        "custom_action_param": {
            "roi": [50, 100, 200, 30],
            "expected": "已完成轮次：\\\\d+",
            "number_regex": "\\\\d+",
            "label": "当前进度"
        },
        "next": ["轮次变化处理"],
        "on_error": ["等待重试"]
    },
    "等待重试": {
        "action": "Wait",
        "post_delay": 2000,
        "next": ["检测轮次变化"]
    }
}

===== 典型流程 =====

检测轮次变化 → 首次(基线=5) → on_error → 等待重试(2s) → 检测轮次变化
                                                                    → 数字不变(5) → on_error → 等待重试 → ...
                                                                    → 数字变化(5→6) → next → 轮次变化处理
                                                                    → 识别失败 → on_error → 等待重试

每轮战斗结束后，游戏自动过渡 6 秒，轮次数字 +1。
RoundTracker 在轮询循环中检测到数字变化即触发 next，执行新轮次处理逻辑。"""