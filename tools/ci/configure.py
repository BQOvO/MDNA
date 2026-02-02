from pathlib import Path

import shutil

assets_dir = Path(__file__).parent.parent.resolve() / "assets"


def configure_ocr_model():
    """配置OCR模型，如果资源不存在则跳过"""
    
    # 检查默认OCR资源路径
    assets_ocr_dir = assets_dir / "MaaCommonAssets" / "OCR"
    
    # 目标OCR目录
    ocr_dir = assets_dir / "resource" / "model" / "ocr"
    
    # 如果目标目录已存在，跳过配置
    if ocr_dir.exists():
        print("Found existing OCR directory, skipping default OCR model import.")
        return
    
    # 如果默认资源不存在，跳过配置（不报错）
    if not assets_ocr_dir.exists():
        print(f"Warning: Default OCR resources not found at {assets_ocr_dir}")
        print("Skipping OCR model configuration - resources will be downloaded during release")
        return
    
    # 复制OCR资源
    shutil.copytree(
        assets_ocr_dir / "ppocr_v5" / "zh_cn",
        ocr_dir,
        dirs_exist_ok=True,
    )
    print("OCR model configured successfully.")


if __name__ == "__main__":
    configure_ocr_model()

    print("OCR model configured.")