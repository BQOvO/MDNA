import shutil
import subprocess

from maa.context import Context
from maa.custom_recognition import CustomRecognition


PACKAGE_NAME = "com.hero.dna.gf"


def _find_adb() -> str | None:
    adb = shutil.which("adb")
    if adb:
        return adb
    candidates = [
        r"E:\MuMuPlayer\nx_main\adb.exe",
        r"D:\MuMuPlayer\nx_main\adb.exe",
        r"C:\Program Files\MuMuPlayer\nx_main\adb.exe",
    ]
    for c in candidates:
        if shutil.which(c) or __import__("os").path.exists(c):
            return c
    return None


class GameProcessCheck(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult | None:
        adb = _find_adb()
        if not adb:
            return None

        try:
            result = subprocess.run(
                [adb, "shell", "pidof", PACKAGE_NAME],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pid_output = result.stdout.strip()
            if pid_output:
                return CustomRecognition.AnalyzeResult(
                    box=[0, 0, 0, 0],
                    detail={"pid": pid_output},
                )
            return None
        except Exception:
            return None