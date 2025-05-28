import mimetypes
import os
import re
from pathlib import Path

from PIL import Image

import config
from services import create_upload_files


def is_image_file(file_path: Path) -> bool:
    """Check if the file is an image by checking its MIME type."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if mime_type not in ["image/jpeg", "image/png"]:
        return False

    if file_path.stat().st_size > 10 * 1024 * 1024:
        return False

    if file_path.stat().st_size < 1024:
        return False

    # check if filename is valid dkp_id-index.ext | dkp_id.ext
    if not re.match(r"^\d+(-\d+)?$", file_path.stem):
        return False

    try:
        Image.open(file_path)
    except Exception:
        return False

    return True


def get_not_uploaded_images(content_dir: Path = Path("content")) -> list[Path]:
    images: list[Path] = []
    for root, _, files in os.walk(content_dir):
        # Check if we're in a not_uploaded directory
        if "not uploaded" not in root:
            continue

        # Create uploaded directory if it doesn't exist
        uploaded_dir = Path(root).with_name("uploaded")
        uploaded_dir.mkdir(parents=True, exist_ok=True)

        # Process each file in the not_uploaded directory
        for file in files:
            file_path = Path(root) / file

            # Check if the file is an image
            if not is_image_file(file_path):
                continue

            images.append(file_path)

    return images


def main():
    images = get_not_uploaded_images(config.content_dir)
    dicts, zips, excels = create_upload_files(images)


if __name__ == "__main__":
    config.config_logger()
    main()
