import logging
from pathlib import Path

import dotenv

dotenv.load_dotenv()

base_dir = Path(__file__).parent.parent

content_dir = base_dir / "content"

tmp_dir = base_dir / "tmp"

content_dir.mkdir(parents=True, exist_ok=True)
tmp_dir.mkdir(parents=True, exist_ok=True)


def config_logger(level: int = logging.INFO):
    LOG_FORMAT = (
        "[{levelname} : {filename}:{lineno} : {asctime} -> {funcName:10}] {message}"
    )

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        style="{",
        handlers=[logging.StreamHandler()],
    )
