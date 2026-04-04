from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context
from numpy import ndarray

TARGET_RATIO = 16.0 / 9.0
TOLERANCE = 0.10

def is_16x9_ratio(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    long_side = max(width, height)
    short_side = min(width, height)
    ratio = long_side / short_side
    return abs(ratio - TARGET_RATIO) <= TARGET_RATIO * TOLERANCE

@AgentServer.custom_recognition("CheckResolution_16_9")
class CheckResolution16_9(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult | None:
        image: ndarray = argv.image
        height, width = image.shape[:2]
        print(f"[CheckResolution] 当前分辨率: {width}x{height}")

        if is_16x9_ratio(width, height):
            print("[CheckResolution] 通过 (16:9 或 9:16) ✅")
            # 识别成功，返回一个有效的 AnalyzeResult（空框即可）
            return CustomRecognition.AnalyzeResult(box=(0, 0, 0, 0), detail="ok")
        else:
            print("[CheckResolution] 失败！停止任务 ❌")
            context.tasker.post_stop()
            # 识别失败，返回 None
            return None