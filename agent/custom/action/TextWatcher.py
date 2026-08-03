import json
import time
import traceback
from maa.context import Context
from maa.custom_action import CustomAction


class TextWatcher(CustomAction):
    CONFIGS = {
        1: {
            "expected": "委托完成",
            "roi": [18, 412, 142, 54],
        },
    }

    DEFAULT_TIMEOUT = 3.0
    DEFAULT_INTERVAL = 0.5

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[TextWatcher] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        config_id = param.get("config", None)
        expected = param.get("expected", None)
        roi = param.get("roi", None)
        timeout = float(param.get("timeout", self.DEFAULT_TIMEOUT))
        interval = float(param.get("interval", self.DEFAULT_INTERVAL))

        if config_id is not None:
            preset = self.CONFIGS.get(config_id)
            if preset is None:
                print(f"[TextWatcher] 未知预设配置 config={config_id}")
                return CustomAction.RunResult(success=False)
            expected = expected or preset["expected"]
            roi = roi or preset.get("roi", None)

        if not expected:
            print("[TextWatcher] 未指定 expected 文本")
            return CustomAction.RunResult(success=False)

        print(f"[TextWatcher] 开始监视文本: \"{expected}\", ROI={roi}, timeout={timeout}s, interval={interval}s")

        start_time = time.monotonic()
        while True:
            if context.tasker.stopping:
                print("[TextWatcher] 任务被停止")
                return CustomAction.RunResult(success=False)

            image = self._screencap(context)
            if image is None:
                return CustomAction.RunResult(success=False)

            if self._ocr_hit(context, image, roi, expected):
                elapsed = time.monotonic() - start_time
                print(f"[TextWatcher] 检测到 \"{expected}\", 耗时 {elapsed:.1f}s")
                return CustomAction.RunResult(success=True)

            if time.monotonic() - start_time >= timeout:
                print(f"[TextWatcher] 超时 ({timeout}s), 未检测到 \"{expected}\"")
                return CustomAction.RunResult(success=False)

            time.sleep(interval)

    def _screencap(self, context):
        try:
            image = context.tasker.controller.post_screencap().wait().get()
            if image is None:
                print("[TextWatcher] 截图为空")
            return image
        except Exception as e:
            print(f"[TextWatcher] 截图失败: {e}")
            traceback.print_exc()
            return None

    def _ocr_hit(self, context, image, roi, pattern):
        entry = "_tw_check"
        node = {
            "recognition": "OCR",
            "expected": [pattern],
        }
        if roi:
            node["roi"] = roi

        pipeline = {entry: node}
        try:
            reco = context.run_recognition(entry, image, pipeline)
            return reco.hit if reco else False
        except Exception:
            return False


"""
===== TextWatcher 功能说明 =====

文本监视器：在指定时间内轮询 OCR 检测目标文本是否出现。
检测到 → success=True → Pipeline 走 next
超时未检测到 → success=False → Pipeline 走 on_error

===== 核心实现 =====

1. 预设配置 (CONFIGS)：类级别字典，key 为 config 编号，value 包含 expected 和 roi。
   config 只影响"找什么"和"在哪找"，不影响 timeout/interval。

2. 轮询循环：每隔 interval 秒截图 → OCR 检测 expected 文本 → 命中则返回成功。

3. 参数合并：param 中的 config 提供默认 expected/roi，param 显式传参可覆盖。

===== 使用教程 =====

用法1：纯预设（最简洁）
  custom_action_param: {"config": 1}
  使用 CONFIGS[1] 的 expected 和 roi，timeout 默认 3s，interval 默认 0.5s。

用法2：预设 + 覆盖部分参数
  custom_action_param: {"config": 1, "timeout": 10.0}
  expected/roi 用预设，timeout 改为 10s。

用法3：完全自定义（不传 config）
  custom_action_param: {
      "expected": "开始挑战",
      "roi": [639, 469, 294, 54],
      "timeout": 5.0,
      "interval": 0.3
  }

===== Pipeline JSON 示例 =====

{
    "检测是否完成委托": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "TextWatcher",
        "custom_action_param": {"config": 1},
        "next": ["结束计时"],
        "on_error": ["超时处理"]
    }
}

===== 如何添加新预设 =====

在 CONFIGS 字典中新增条目即可：
CONFIGS = {
    1: {"expected": "委托完成", "roi": [18, 412, 142, 54]},
    2: {"expected": "加载中",   "roi": [1184, 632, 71, 61]},
    3: {"expected": "再次进行", "roi": [764, 619, 508, 90]},
}
Pipeline 中只需 {"config": 2} 即可使用。
"""