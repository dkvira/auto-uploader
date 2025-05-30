

import config
from services import create_upload_files, get_not_uploaded_images


def main():
    images = get_not_uploaded_images(config.content_dir)
    key, dicts, zips, excels = create_upload_files(images)


if __name__ == "__main__":
    config.config_logger()
    main()
