import asyncio

from src import config, services, uploader


async def main():
    images = services.get_not_uploaded_images(config.content_dir)
    key, _, _, _ = services.create_upload_files(images)

    await uploader.upload_key_dir(key)


if __name__ == "__main__":
    asyncio.run(main())
