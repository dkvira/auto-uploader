import asyncio
import json
import logging
import os
import re
import shutil
from pathlib import Path

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from . import basic, config
from .login import AuthenticatedClient


async def upload_zip(filepath: Path, cookies: dict | httpx.Cookies | None = None):
    url = "https://admin.digikala.com/auto/assign/product/photo/file/item/0/"
    params = {"_back": "https://admin.digikala.com/auto/assign/product/photo/file/"}

    # Prepare the multipart form data
    files = {"files[]": (filepath.name, open(filepath, "rb"), "application/zip")}

    data = {
        "name": "file",
        "namespace": "444",
        "file_uploader": "1",
        "multiple": "false",
        "file_type": "file",
        "responseType": "json",
        "is_private": "1",
    }

    headers = {
        "Accept": "*/*",
        "Origin": "https://admin.digikala.com",
        "Referer": url + "?" + "_back=" + params["_back"],
    }

    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.post(
            url,
            params=params,
            files=files,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )

    return response.json()


async def submit_uploaded_file(
    upload_response: dict, name: str, cookies: dict | httpx.Cookies | None = None
):
    url = "https://admin.digikala.com/auto/assign/product/photo/file/item/0/"
    params = {"_back": "https://admin.digikala.com/auto/assign/product/photo/file/"}

    # Prepare the form data with the uploaded file information
    data = {
        "name": name,
        "file": json.dumps(
            [
                {
                    "id": upload_response.get("data", {}).get("id"),
                    "name": upload_response.get("data", {}).get("name"),
                    "size": upload_response.get("data", {}).get("size"),
                    "temporary": True,
                    "url": upload_response.get("data", {}).get("url"),
                }
            ]
        ),
        "active": "1",
        "crud_tab_id": "main",
    }

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://admin.digikala.com",
        "Referer": url + "?" + "_back=" + params["_back"],
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }

    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.post(
            url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )

    return response


async def check_zip_upload_table_status(
    name: str, cookies: dict | httpx.Cookies | None = None
):
    url = "https://admin.digikala.com/auto/assign/product/photo/file/"

    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.get(
            url,
            headers={"Origin": "https://admin.digikala.com"},
            cookies=cookies,
            timeout=60,
        )

    soup = BeautifulSoup(response.text, "html.parser")
    table_form = soup.find(id="tableForm")

    if not table_form:
        return None

    table = table_form.find("table")
    if not table:
        return None

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        if cells[0].text.strip() != name:
            continue

        if cells[3].text.strip() == "Done":
            return True
        return False

    return None


async def check_zip_upload_status(
    name: str, cookies: dict | httpx.Cookies | None = None
):
    for _ in range(100):
        upload_response = await check_zip_upload_table_status(name, cookies)
        if upload_response is None:
            return None

        if upload_response:
            return upload_response

        await asyncio.sleep(5)


@basic.retry_execution(attempts=3, delay=1)
async def process_zip_import(
    filepath: Path, cookies: dict | httpx.Cookies | None = None
):
    upload_response_data = await upload_zip(filepath, cookies)
    logging.debug(f"Zip upload response: {upload_response_data}")
    submit_response = await submit_uploaded_file(
        upload_response_data, filepath.stem, cookies
    )
    logging.debug(f"Zip submit response: {submit_response.status_code}")
    await check_zip_upload_status(filepath.stem, cookies)
    return submit_response


async def export_excel_template(
    title: str, cookies: dict | httpx.Cookies | None = None
):
    """Step 1: Export the excel template and get the exported file info"""
    # Initial export request
    url = "https://admin.digikala.com/excel-imports/item/0/"
    params = {"_back": "https://admin.digikala.com/excel-imports/"}

    data = {
        "title": title,
        "template_type": "auto_assign_products_photo",
        "excel_mode": "export",
        "crud_tab_id": "main",
        # All filter fields defaulting to empty string or '0'
        "filters_from_date": "",
        "filters_to_date": "",
        # ... other filter fields with default values
    }

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://admin.digikala.com",
        "Referer": url + "?" + "_back=" + params["_back"],
        "Upgrade-Insecure-Requests": "1",
    }

    # Make initial request
    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        export_response = await client.post(
            url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )

    # Extract redirect URL from response
    soup = BeautifulSoup(export_response.text, "html.parser")
    redirect_url = soup.find("a")["href"]
    if not redirect_url:
        raise Exception("Failed to get redirect URL from export response")

    # Follow redirect to get the exported file info
    full_redirect_url = f"https://admin.digikala.com{redirect_url}"
    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        redirect_response = await client.get(
            full_redirect_url,
            cookies=cookies,
            timeout=60,
        )

    # Parse the response to get the exported file info
    soup = BeautifulSoup(redirect_response.text, "html.parser")
    # Look for the exported file info in a hidden input or form field
    exported_file_field = soup.find("input", {"name": "exported_file"})
    if not exported_file_field:
        raise Exception("Could not find exported file info in response")

    return exported_file_field["value"], redirect_url.split("/")[3]


async def upload_excel_file(
    title: str, excel_filepath: Path, cookies: dict | httpx.Cookies | None = None
):
    """Step 2: Upload the excel file and get the imported file info"""
    url = "https://admin.digikala.com/excel-imports/item/154298/"
    params = {"_back": "https://admin.digikala.com/excel-imports/"}

    # Create form data with file
    files = {
        "files[]": (
            excel_filepath.name,
            open(excel_filepath, "rb"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }

    data = {
        "name": "imported_file",
        "namespace": "60",
        "file_uploader": "1",
        "multiple": "false",
        "file_type": "file",
        "responseType": "json",
        "is_private": "1",
    }

    headers = {
        "Accept": "*/*",
        "Origin": "https://admin.digikala.com",
        "Referer": url + "?" + "_back=" + params["_back"],
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    # Upload the file
    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.post(
            url,
            params=params,
            data=data,
            files=files,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )

    # Parse JSON response
    if response.status_code != 200:
        raise Exception(f"File upload failed with status {response.status_code}")

    response_data = response.json()
    if not response_data:
        raise Exception("No response data from file upload")

    return response_data


async def import_excel_file(
    title: str,
    exported_file_info: str,
    imported_file_info: dict,
    upload_id: str,
    cookies: dict | httpx.Cookies | None = None,
):
    """Step 3: Import the uploaded excel file"""
    url = f"https://admin.digikala.com/excel-imports/item/{upload_id}/"
    params = {"_back": "https://admin.digikala.com/excel-imports/"}

    # Format the imported file info as needed
    imported_file_data = [
        {
            "id": imported_file_info["data"]["id"],
            "name": imported_file_info["data"]["name"],
            "size": imported_file_info["data"]["size"],
            "temporary": imported_file_info["data"]["temporary"],
            "url": imported_file_info["data"]["url"],
        }
    ]

    data = {
        "title": title,
        "template_type": "auto_assign_products_photo",
        "exported_file": exported_file_info,  # Already in correct format
        "imported_file": json.dumps(imported_file_data),
        "excel_mode": "import",
        "crud_tab_id": "main",
        # All filter fields defaulting to empty string or '0'
        "filters_from_date": "",
        "filters_to_date": "",
        # ... other filter fields with default values
        "filters_creation_type": "",
        "filters_marketplace_financial_notation_id": "0",
        "filters_conditional": "",
        "filters_business_channel": "",
        "filters_seller_bucket": "",
        "filters_start_date": "",
        "filters_seller_id": "0",
        "filters_digiclub_voucher_id": "0",
        "filters_digiclub_spinner_voucher_id": "0",
        "filters_digiclub_extra_point_id": "0",
        "filters_digiclub_game_voucher_id": "0",
        "filters_digikala_referral_campaign": "0",
        "filters_bp_contract_id": "0",
        "filters_third_party_voucher_id": "0",
        "filters_lucky_draw_voucher_id": "0",
        "filters_mission_id": "0",
        "filters_digiclub_product_reward_id": "0",
        "filters_category_id": "0",
        "filters_tag_id": "0",
        "filters_brand_id": "0",
        "filters_last_order_date_from": "",
        "filters_last_order_date_to": "",
        "filters_stock_count_less": "",
        "filters_stock_count_greater": "",
        "filters_available_stock": "",
        "filters_last_purchase_supplier_id": "0",
        "filters_last_purchase_date_from": "",
        "filters_last_purchase_date_to": "",
        "filters_dkpc_is_active": "",
        "filters_main_supply_category_id": "0",
        "filters_register_seller_date_from": "",
        "filters_register_seller_date_to": "",
        "filters_training_date_from": "",
        "filters_training_date_to": "",
        "filters_supply_category": "0",
        "filters_brand_id_nature": "0",
        "filters_autofix_type": "",
        "filters_notation_id": "0",
        "filters_event_from_date": "",
        "filters_event_to_date": "",
        "filters_product_variant_id": "0",
        "filters_receipt_id": "",
        "filters_supply_order_id": "0",
        "filters_manual_cost_marketplace_financial_notation_id": "0",
        "filters_event_date": "",
        "filters_description": "",
        "filters_unique_size_category_id": "0",
        "filters_marketplace_seller_id": "0",
        "filters_size_category_id": "0",
    }

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Origin": "https://admin.digikala.com",
        "Referer": url + "?" + "_back=" + params["_back"],
        "Upgrade-Insecure-Requests": "1",
    }

    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.post(
            url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )

    return response


async def check_excel_upload_table_status(
    name: str, cookies: dict | httpx.Cookies | None = None
):
    """Check the status of an excel import in the table"""
    url = "https://admin.digikala.com/excel-imports/"

    async with httpx.AsyncClient(proxy=os.getenv("DIGIKALA_PROXY")) as client:
        response = await client.get(
            url,
            headers={"Origin": "https://admin.digikala.com"},
            cookies=cookies,
            timeout=60,
        )
    soup = BeautifulSoup(response.text, "html.parser")
    table_form = soup.find(id="tableForm")

    if not table_form:
        return None

    table = table_form.find("table")
    if not table:
        return None

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        if cells[2].text.strip() != name:
            continue

        if cells[5].text.strip() == "Imported":
            return cells[1].text.strip()

        if cells[5].text.strip() == "Invalid":
            logging.warning(f"Invalid excel file {name}")
            raise Exception("Invalid excel file upload")

        return False

    return None


async def check_excel_upload_status(
    name: str, cookies: dict | httpx.Cookies | None = None
):
    """Poll the excel import status until complete"""
    for _ in range(100):
        upload_response = await check_excel_upload_table_status(name, cookies)
        if upload_response is None:
            return None

        if upload_response:
            return upload_response

        await asyncio.sleep(5)


async def process_excel_import(
    title: str, excel_filepath: Path, cookies: dict | httpx.Cookies | None = None
) -> str:
    """Handle the complete excel import process"""
    # Step 1: Export template and get exported file info
    exported_file_info, upload_id = await export_excel_template(title, cookies)
    if not exported_file_info:
        raise Exception("Failed to get exported file info")

    # Step 2: Upload excel file and get imported file info
    imported_file_info = await upload_excel_file(title, excel_filepath, cookies)
    if not imported_file_info:
        raise Exception("Failed to get imported file info")

    # Step 3: Import the uploaded file
    import_response = await import_excel_file(
        title, exported_file_info, imported_file_info, upload_id, cookies
    )
    if import_response.status_code >= 400:
        raise Exception(f"Failed to import excel: {import_response.status_code}")

    logging.debug(f"Excel import response: {import_response.status_code}")
    # Step 4: Check import status
    excel_upload_id = await check_excel_upload_status(title, cookies)
    if not excel_upload_id:
        raise Exception("Excel import failed or timed out")

    return excel_upload_id


async def download_unzip(url: str, filepath: Path):
    import zipfile

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        with open(filepath, "wb") as f:
            f.write(response.content)

    with zipfile.ZipFile(filepath, "r") as zip_ref:
        zip_ref.extractall(filepath.parent)


def check_connection():
    client = AuthenticatedClient()
    response = client.get("https://admin.digikala.com", timeout=10)
    return response.status_code


def save_report_excel(*, key: str, uploaded_images: list[str], excel_upload_id: str):
    # check if report excel exists
    # load data from report excel
    # add new records to report excel
    # data is (original_image_path, status, excel_upload_id, key)
    # save report excel
    status = "success" if excel_upload_id else "failed"
    report_excel_path = config.log_dir / "report.xlsx"
    new_df = pd.DataFrame(
        {
            "key": [key] * len(uploaded_images),
            "original_image_path": uploaded_images,
            "image_path": [
                p.replace("not uploaded", "uploaded") for p in uploaded_images
            ],
            "status": [status] * len(uploaded_images),
            "excel_upload_id": [excel_upload_id] * len(uploaded_images),
        }
    )
    if not report_excel_path.exists():
        new_df.to_excel(report_excel_path, index=False)
    else:
        df = pd.read_excel(report_excel_path)
        df = pd.concat([df, new_df], ignore_index=True)
        df.to_excel(report_excel_path, index=False)

    return uploaded_images


def post_process(*, key: str, index: int, excel_upload_id: str):
    basedir = config.tmp_dir / key
    dicts_path = basedir / f"dicts_{key}.json"
    if not dicts_path.exists():
        logging.warning(f"dicts_{key}.json not found")
        return

    with open(dicts_path, encoding="utf-8") as f:
        dicts: list[dict[str, str]] = json.load(f)

    uploaded_images: list[str] = list(dicts[index].values())
    save_report_excel(
        key=key, uploaded_images=uploaded_images, excel_upload_id=excel_upload_id
    )

    for image_path in uploaded_images:
        # move from not uploaded to uploaded
        src_path = Path(image_path)
        if not src_path.exists():
            continue

        # Get the parent directory and create uploaded directory
        parent_dir = str(src_path.parent)
        uploaded_dir = Path(parent_dir.replace("not uploaded", "uploaded"))
        uploaded_dir.mkdir(parents=True, exist_ok=True)

        # Move the file to uploaded directory
        dst_path = uploaded_dir / src_path.name
        shutil.move(str(src_path), str(dst_path))


async def upload_key_dir(key: str):
    logging.info("=" * 40)
    logging.info(f"Uploading key: {key}")
    logging.info("-" * 40)

    client = AuthenticatedClient()
    response = client.login()
    cookies = response.cookies
    
    basedir = config.tmp_dir / key
    zips = sorted(list(basedir.glob("*.zip")))
    excels = list(
        map(
            lambda x: (basedir / x.stem.replace("zip", "excel")).with_suffix(".xlsx"),
            zips,
        )
    )
    pairs = list(zip(zips, excels, strict=False))

    for i, (zip_path, excel_path) in enumerate(pairs):
        logging.info("-" * 40)
        logging.info(f"Processing file {i + 1}/{len(pairs)}")

        if not zip_path.exists() or not excel_path.exists():
            # generate string that which one of zip_path or excel_path,
            # if both are not found, say both are not found
            not_found_str = (
                f"zip_path: {zip_path} not found"
                if not zip_path.exists()
                else (
                    f"excel_path: {excel_path} not found"
                    if not excel_path.exists()
                    else "both zip_path and excel_path are not found"
                )
            )
            logging.warning(f"file {i + 1}/{len(pairs)} {not_found_str}")
            continue

        # Upload and process zip file
        zip_response = await process_zip_import(zip_path, cookies)
        logging.info(
            f"Zip upload {i + 1}/{len(zips)} "
            + ("OK" if zip_response.status_code < 400 else "FAILED")
        )

        # Process excel file
        excel_upload_id = await process_excel_import(
            excel_path.stem, excel_path, cookies
        )
        logging.info(
            f"Excel import {i + 1}/{len(zips)} "
            + ("OK" if excel_upload_id else "FAILED")
        )

        index = int(zip_path.stem.split("_")[-1]) - 1
        post_process(
            key=key,
            index=index,
            excel_upload_id=excel_upload_id,
        )

    shutil.rmtree(basedir)


if __name__ == "__main__":
    config.config_logger()
    # main(sys.argv[1])
    logging.info(f"Connection status: {'OK' if check_connection() < 400 else 'FAILED'}")
    key = next(
        filter(
            lambda x: x.is_dir()
            and re.match(r"^\d{4}-\d{2}-\d{2}_[a-zA-Z0-9]+$", x.name),
            config.tmp_dir.iterdir(),
        )
    ).name
    asyncio.run(upload_key_dir(key))
