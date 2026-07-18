from pathlib import Path
import shutil

# 项目根目录（configure.py 在 tools/ 下，因此 parent.parent）
root_dir = Path(__file__).parent.parent.resolve()

def configure_ocr_model():
    # 源路径：MaaCommonAssets 子模块中的 OCR 模型
    src = root_dir / "MaaCommonAssets" / "OCR" / "ppocr_v6" / "small"
    dst = root_dir / "resource" / "model" / "ocr"

    if src.exists():
        if not dst.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print("OCR model copied from MaaCommonAssets")
        else:
            print("OCR directory already exists, skipping copy.")
    else:
        # 如果源不存在，打印警告但不中断构建（因为模型可能已存在）
        print(f"OCR source not found: {src}. Assuming model already exists in resource/model/ocr")

if __name__ == "__main__":
    configure_ocr_model()
    print("OCR model configured.")