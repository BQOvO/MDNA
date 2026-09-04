import json
import re
import time
import traceback
from maa.context import Context
from maa.custom_action import CustomAction
from ..utils.Logger import Logger


class RoundTracker(CustomAction):
    _last_values = {}
    MAX_RETRIES = 5

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        roi = [155, 222, 45, 33]

        entry = argv.task_detail.entry
        last = self._last_values.get(entry)
        logger = Logger("RoundTracker", context)

        number = None
        for retry in range(1, self.MAX_RETRIES + 1):
            image = self._screencap(context)
            if image is None:
                print(f"[RoundTracker] 第{retry}次截图失败, 等待1秒重试")
                time.sleep(1)
                continue

            text = self._ocr_recognize(context, image, roi)
            if text is None:
                print(f"[RoundTracker] 第{retry}次 OCR 识别失败, 等待1秒重试")
                time.sleep(1)
                continue

            match = re.search(r"\d+", text)
            if not match:
                print(f"[RoundTracker] 第{retry}次 未提取到数字: \"{text}\", 等待1秒重试")
                time.sleep(1)
                continue

            number = match.group()
            break

        if number is None:
            print(f"[RoundTracker] 已达最大重试次数 {self.MAX_RETRIES}, 返回失败")
            return CustomAction.RunResult(success=False)

        if last is None:
            self._last_values.clear()
            self._last_values[entry] = number
            logger.ui(f"第{number}轮挂机开始")
            print(f"[RoundTracker] 首次识别(基线): {number}, 走 on_error 继续轮询")
            return CustomAction.RunResult(success=False)

        if last == number:
            print(f"[RoundTracker] 数值未变化: {number}, 跳过输出, 走 on_error 继续轮询")
            return CustomAction.RunResult(success=False)

        self._last_values[entry] = number
        logger.ui(f"第{number}轮挂机开始")
        print(f"[RoundTracker] 数值变化: {last} → {number}, 走 next")
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

    def _ocr_recognize(self, context, image, roi):
        entry = "_rt_ocr"
        node = {
            "recognition": "OCR",
            "roi": roi,
            "expected": ["\\d+"],
        }
        pipeline = {entry: node}
        try:
            reco = context.run_recognition(entry, image, pipeline)
            if reco and reco.hit and reco.best_result:
                best = reco.best_result
                if hasattr(best, "text"):
                    return best.text
                return str(best)
            return None
        except Exception as e:
            print(f"[RoundTracker] OCR 识别异常: {e}")
            traceback.print_exc()
            return None


"""
===== RoundTracker 功能说明 =====

轮次进度追踪器：OCR 识别 ROI 中的数字，与上一次识别结果对比。
用于轮询检测游戏自动进轮次（6秒过渡后轮次数字+1）。

内部重试机制：OCR 失败时等待 1 秒重试，最多 20 次，应对游戏卡顿。

===== 核心实现 =====

1. OCR 识别：在 ROI 区域内 OCR 匹配数字（\\d+）。
2. 重试保护：截图/OCR 失败 → 等待 1 秒 → 重试，最多 20 次。
3. 状态追踪：类级别 _last_values 按 entry 隔离，只存数字。
4. 变化检测：
   - 首次识别 → UI 输出 "第N轮挂机开始"（前缀由 Logger 全局统一添加），记录基线，走 on_error
   - 数字相同 → 跳过 UI，走 on_error（还在同一轮，继续等待）
   - 数字变化 → UI 输出 "第N轮挂机开始"，更新基线，走 next
   - 重试耗尽 → 走 on_error

===== 使用教程 =====

参数格式：
{
    "roi": [x, y, w, h]   // OCR 识别区域（必填，只识别数字）
}

===== Pipeline JSON 示例 =====

{
    "检测轮次变化": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "RoundTracker",
        "custom_action_param": {
            "roi": [50, 100, 200, 30]
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

检测轮次变化 → 首次(基线=1) → UI: "第1轮挂机开始" → on_error → 等待重试(2s)
→ 检测轮次变化 → 数字不变(1) → 跳过UI → on_error → 等待重试 → ...
→ 检测轮次变化 → 数字变化(1→2) → UI: "第2轮挂机开始" → next → 轮次变化处理

每轮战斗结束后，游戏自动过渡 6 秒，轮次数字 +1。
RoundTracker 内部有 20 次重试保护，应对 OCR 偶发失败和游戏卡顿。

===== 类常量配置 =====

MAX_RETRIES = 20   // OCR 失败重试次数（每次间隔 1 秒）
"""