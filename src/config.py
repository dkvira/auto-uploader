import logging
import logging.config
import tomllib
from pathlib import Path

import dotenv

dotenv.load_dotenv()

base_dir = Path(__file__).parent.parent

with open(base_dir / "config.toml", "rb") as f:
    content_config: dict[str, str] = tomllib.load(f).get("content", {})

content_dir = content_config.get("content_dir", base_dir / "content")
tmp_dir = base_dir / "tmp"
log_dir = base_dir / "logs"

content_dir.mkdir(parents=True, exist_ok=True)
tmp_dir.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)


def config_logger(level: int = logging.INFO):
    log_config = {
        "formatters": {
            "standard": {
                "format": "[{levelname} : {filename:>15}:{lineno:4} : {asctime} -> "
                "{funcName:>18}] {message}",
                "style": "{",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "standard",
            },
            "file": {
                "class": "logging.FileHandler",
                "level": level,
                "filename": log_dir / "app.log",
                "formatter": "standard",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": True,
            },
            "httpx": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": True,
            },
        },
        "version": 1,
    }
    logging.config.dictConfig(log_config)
