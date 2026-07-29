import json
import time
import traceback
from maa.context import Context
from maa.custom_action import CustomAction


class NumberComparator(CustomAction):
    ROI = [1030,428,86,28]
    CLICK_LESS = [1180, 475]
    CLICK_GREATER = [965, 475]
    CLICK_WHEN_ONE = [1210, 416]
    CLICK_OPEN = [1200, 480]
    MAX_RETRIES = 200

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[NumberComparator] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        target = int(param.get("target", 1))

        image = self._screencap(context)
        if image is None:
            return CustomAction.RunResult(success=False)

        has_text = self._ocr_hit(context, image, self.ROI, "\\d+/\\d+")

        if target == 1:
            if has_text:
                self._click(context, self.CLICK_WHEN_ONE, "target=1, 检测到文字, 点击取消自动轮次")
                return CustomAction.RunResult(success=True)
            else:
                print("[NumberComparator] target=1, 未检测到文字, 跳过点击, 继续执行 next")
                return CustomAction.RunResult(success=True)

        if not has_text:
            self._click(context, self.CLICK_OPEN, "未检测到轮次文字, 点击开启自动轮次")
            time.sleep(0.5)

        for attempt in range(1, self.MAX_RETRIES + 1):
            time.sleep(0.3)
            image = self._screencap(context)
            if image is None:
                return CustomAction.RunResult(success=False)

            has_text = self._ocr_hit(context, image, self.ROI, "\\d+/\\d+")
            if not has_text:
                self._click(context, self.CLICK_OPEN, "轮次文字消失, 点击开启自动轮次")
                continue

            recognized = self._find_number(context, image, target)
            if recognized is None:
                print("[NumberComparator] 未能识别轮次数字")
                return CustomAction.RunResult(success=False)

            print(f"[NumberComparator] 第{attempt}次 识别={recognized}, 目标={target-1}, 比较: {recognized}+1 vs {target}")
            if recognized + 1 == target:
                print(f"[NumberComparator] {recognized}+1 == {target}, 成功!")
                return CustomAction.RunResult(success=True)
            elif recognized + 1 > target:
                self._click(context, self.CLICK_GREATER, f"{recognized}+1 > {target}, 点击调小")
            else:
                self._click(context, self.CLICK_LESS, f"{recognized}+1 < {target}, 点击调大")

        print(f"[NumberComparator] 已达最大重试次数 {self.MAX_RETRIES}, 返回失败")
        return CustomAction.RunResult(success=False)

    def _click(self, context, pos, msg):
        if pos and len(pos) >= 2:
            x, y = pos[0], pos[1]
            print(f"[NumberComparator] {msg} ({x}, {y})")
            context.tasker.controller.post_click(x, y).wait()

    def _screencap(self, context):
        try:
            image = context.tasker.controller.post_screencap().wait().get()
            if image is None:
                print("[NumberComparator] 截图为空")
            return image
        except Exception as e:
            print(f"[NumberComparator] 截图失败: {e}")
            traceback.print_exc()
            return None

    def _ocr_hit(self, context, image, roi, pattern):
        entry = "_nc_presence"
        pipeline = {
            entry: {
                "recognition": "OCR",
                "roi": roi,
                "expected": [pattern],
            }
        }
        try:
            reco = context.run_recognition(entry, image, pipeline)
            return reco.hit if reco else False
        except Exception:
            return False

    def _find_number(self, context, image, target):
        center = target - 1
        if center < 1:
            center = 1

        max_n = 99
        for offset in range(0, max(center, max_n - center) + 1):
            for n in (center - offset, center + offset):
                if 1 <= n <= max_n:
                    if self._ocr_hit(context, image, self.ROI, f"{n}/"):
                        print(f"[NumberComparator] 扫描定位到数字: {n}")
                        return n
        return None