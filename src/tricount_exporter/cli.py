from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import openpyxl
import requests
import rsa
from tqdm import tqdm

from . import __version__

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "tricount-exporter" / "config.toml"
INFO_FILE_NAME = "tricount-info.json"


def sanitize_path_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return sanitized.strip("-") or "tricount"


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_tricount_info(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return None


def directory_matches_tricount_key(directory: Path, tricount_key: str) -> bool:
    info = load_tricount_info(directory / INFO_FILE_NAME)
    return bool(info and info.get("tricount_key") == tricount_key)


def resolve_export_directory(base_output_dir: Path, title: str, tricount_key: str) -> Path:
    base_name = sanitize_path_component(title)
    short_key = sanitize_path_component(tricount_key)[-6:]
    suffix_index = 0

    while True:
        suffix = ""
        if suffix_index >= 1:
            suffix = f"-{short_key}"
        if suffix_index >= 2:
            suffix = f"-{short_key}-{suffix_index}"

        candidate = base_output_dir / f"{base_name}{suffix}"
        if not candidate.exists() or directory_matches_tricount_key(candidate, tricount_key):
            return candidate

        suffix_index += 1


def write_tricount_info(
    export_dir: Path, tricount_title: str, tricount_key: str, source_url: str
) -> None:
    info = {
        "title": tricount_title,
        "tricount_key": tricount_key,
        "downloaded_at": current_timestamp(),
        "source_url": source_url,
    }
    info_path = export_dir / INFO_FILE_NAME
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")


@dataclass
class AppConfig:
    tricount_key: str | None = None
    output_dir: Path = Path.home() / "Downloads"
    download_attachments: bool = True
    write_excel: bool = False
    write_sesterce: bool = False
    save_response: bool = False
    response_file_name: str = "response_data.json"


class TricountAPI:
    def __init__(self) -> None:
        self.base_url = "https://api.tricount.bunq.com"
        self.app_installation_id = str(uuid.uuid4())
        self.public_key, self.private_key = rsa.newkeys(2048)
        self.rsa_public_key_pem = self.public_key.save_pkcs1(format="PEM").decode()
        self.headers = {
            "User-Agent": "com.bunq.tricount.android:RELEASE:7.0.7:3174:ANDROID:13:C",
            "app-id": self.app_installation_id,
            "X-Bunq-Client-Request-Id": "049bfcdf-6ae4-4cee-af7b-45da31ea85d0",
        }
        self.auth_token: str | None = None
        self.user_id: int | None = None

    def authenticate(self) -> None:
        auth_url = f"{self.base_url}/v1/session-registry-installation"
        auth_payload = {
            "app_installation_uuid": self.app_installation_id,
            "client_public_key": self.rsa_public_key_pem,
            "device_description": "Android",
        }
        response = requests.post(auth_url, json=auth_payload, headers=self.headers, timeout=30)
        response.raise_for_status()
        auth_data = response.json()

        response_items = auth_data["Response"]
        self.auth_token = next(item["Token"]["token"] for item in response_items if "Token" in item)
        self.user_id = next(
            item["UserPerson"]["id"] for item in response_items if "UserPerson" in item
        )
        self.headers["X-Bunq-Client-Authentication"] = self.auth_token

    def fetch_tricount_data(self, tricount_key: str) -> dict[str, Any]:
        if self.user_id is None:
            raise RuntimeError("authenticate() must be called before fetch_tricount_data()")
        tricount_url = (
            f"{self.base_url}/v1/user/{self.user_id}/registry"
            f"?public_identifier_token={tricount_key}"
        )
        response = requests.get(tricount_url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


class TricountHandler:
    @staticmethod
    def get_tricount_title(data: dict[str, Any]) -> str:
        return cast(str, data["Response"][0]["Registry"]["title"])

    @staticmethod
    def parse_tricount_data(
        data: dict[str, Any],
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
        registry = data["Response"][0]["Registry"]
        memberships = [
            {"Name": member["RegistryMembershipNonUser"]["alias"]["display_name"]}
            for member in registry["memberships"]
        ]

        transactions: list[dict[str, Any]] = []
        for entry in registry["all_registry_entry"]:
            transaction = entry["RegistryEntry"]
            who_paid = transaction["membership_owned"]["RegistryMembershipNonUser"]["alias"][
                "display_name"
            ]
            shares = {
                allocation["membership"]["RegistryMembershipNonUser"]["alias"]["display_name"]: abs(
                    float(allocation["amount"]["value"])
                )
                for allocation in transaction["allocations"]
            }

            transactions.append(
                {
                    "Type": transaction["type_transaction"],
                    "Who Paid": who_paid,
                    "Total": float(transaction["amount"]["value"]) * -1,
                    "Currency": transaction["amount"]["currency"],
                    "Description": transaction.get("description", ""),
                    "When": transaction["date"],
                    "Shares": shares,
                    "Category": transaction["category"],
                    "Attachments": transaction.get("attachment", []),
                }
            )

        return memberships, transactions

    @staticmethod
    def download_attachments(transactions: list[dict[str, Any]], download_folder: Path) -> None:
        download_folder.mkdir(parents=True, exist_ok=True)
        file_counter = 1
        total_files = sum(len(transaction["Attachments"]) for transaction in transactions)
        print(f"Total attachments: {total_files}")

        if total_files == 0:
            return

        with tqdm(total=total_files, desc="Downloading attachments") as progress_bar:
            for transaction in transactions:
                attachment_files: list[str] = []
                for attachment in transaction["Attachments"]:
                    if "urls" not in attachment or not attachment["urls"]:
                        continue
                    url = attachment["urls"][0]["url"]
                    extension = os.path.splitext(url.split("?")[0])[1] or ".file"
                    file_name = f"receipt_{file_counter}{extension}"
                    file_path = download_folder / file_name
                    TricountHandler.download_file(url, file_path)
                    attachment_files.append(file_name)
                    file_counter += 1
                    progress_bar.update(1)
                transaction["File Names"] = ", ".join(attachment_files)

    @staticmethod
    def download_file(url: str, file_path: Path) -> None:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        file_path.write_bytes(response.content)

    @staticmethod
    def prepare_transaction_data(transaction: dict[str, Any]) -> list[Any]:
        involved = ", ".join(name for name, amount in transaction["Shares"].items() if amount > 0)
        attachment_urls = ", ".join(
            attachment["urls"][0]["url"]
            for attachment in transaction["Attachments"]
            if "urls" in attachment and attachment["urls"]
        )

        return [
            transaction["Who Paid"],
            transaction["Total"],
            transaction["Currency"],
            transaction["Description"],
            datetime.strptime(transaction["When"], "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d"),
            involved,
            transaction.get("File Names", ""),
            attachment_urls,
            transaction["Category"],
        ]

    @staticmethod
    def prepare_sesterce_transaction_data(
        transaction: dict[str, Any], members: list[str]
    ) -> list[Any]:
        paid_by = [0.0] * len(members)
        payer = transaction["Who Paid"]
        paid_by[members.index(payer)] = transaction["Total"]

        paid_for = [0.0] * len(members)
        for paid_for_member, amount in transaction["Shares"].items():
            paid_for[members.index(paid_for_member)] = amount

        category = ""
        type_transaction = transaction["Type"]
        if type_transaction == "BALANCE":
            category = "Money Transfer"
        elif type_transaction == "INCOME":
            paid_for = [-amount for amount in paid_for]
            if transaction["Category"] != "UNCATEGORIZED":
                category = transaction["Category"]
        elif type_transaction == "NORMAL" and transaction["Category"] != "UNCATEGORIZED":
            category = transaction["Category"]

        return [
            datetime.strptime(transaction["When"], "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d"),
            transaction["Description"],
            *paid_by,
            *paid_for,
            transaction["Currency"],
            category,
        ]

    @staticmethod
    def write_to_excel(transactions: list[dict[str, Any]], file_path: Path) -> None:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Tricount Transactions"

        headers = [
            "Who Paid",
            "Total",
            "Currency",
            "Description",
            "When",
            "Involved",
            "File Names",
            "Attachment URLs",
            "Category",
        ]
        sheet.append(headers)

        for transaction in transactions:
            sheet.append(TricountHandler.prepare_transaction_data(transaction))

        workbook.save(file_path)
        print(f"Transactions saved to {file_path}")

    @staticmethod
    def write_to_csv(transactions: list[dict[str, Any]], file_path: Path) -> None:
        with file_path.open("w", encoding="utf-8", newline="") as csv_file:
            headers = [
                "Who Paid",
                "Total",
                "Currency",
                "Description",
                "When",
                "Involved",
                "File Names",
                "Attachment URLs",
                "Category",
            ]
            transaction_writer = csv.writer(csv_file, delimiter=";")
            transaction_writer.writerow(headers)
            for transaction in transactions:
                transaction_writer.writerow(TricountHandler.prepare_transaction_data(transaction))

        print(f"Transactions saved to {file_path}")

    @staticmethod
    def write_to_sesterce_csv(
        memberships: list[dict[str, str]],
        transactions: list[dict[str, Any]],
        file_path: Path,
    ) -> None:
        members = sorted(member["Name"] for member in memberships)

        with file_path.open("w", encoding="utf-8", newline="") as csv_file:
            headers = (
                ["Date", "Title"]
                + [f"Paid by {member}" for member in members]
                + [f"Paid for {member}" for member in members]
                + ["Currency", "Category"]
            )
            transaction_writer = csv.writer(csv_file, delimiter=",")
            transaction_writer.writerow(headers)
            for transaction in transactions:
                row_data = TricountHandler.prepare_sesterce_transaction_data(transaction, members)
                transaction_writer.writerow(row_data)

        print(f"Sesterce export saved to {file_path}")


def load_config(config_path: Path | None) -> AppConfig:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return AppConfig()

    with path.open("rb") as handle:
        raw_config = tomllib.load(handle)

    return AppConfig(
        tricount_key=raw_config.get("tricount_key"),
        output_dir=Path(raw_config.get("output_dir", "~/Downloads")).expanduser(),
        download_attachments=parse_bool(
            raw_config.get("download_attachments"), AppConfig.download_attachments
        ),
        write_excel=parse_bool(raw_config.get("write_excel"), AppConfig.write_excel),
        write_sesterce=parse_bool(raw_config.get("write_sesterce"), AppConfig.write_sesterce),
        save_response=parse_bool(raw_config.get("save_response"), AppConfig.save_response),
        response_file_name=raw_config.get("response_file_name", "response_data.json"),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download transactions from a public Tricount key and export them to"
            " title-based output folders."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tricount-exporter {__version__}",
    )
    parser.add_argument(
        "--key",
        help="Public Tricount key. Overrides any value set in the config file.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Optional TOML config file. Defaults to {DEFAULT_CONFIG_PATH}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Base output directory. A title-based subdirectory is created inside it.",
    )
    parser.add_argument(
        "--download-attachments",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable attachment downloads.",
    )
    parser.add_argument(
        "--write-excel",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable Excel export.",
    )
    parser.add_argument(
        "--write-sesterce",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable Sesterce CSV export.",
    )
    parser.add_argument(
        "--save-response",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Save the raw JSON API response into the title-based output directory.",
    )
    return parser


def resolve_settings(args: argparse.Namespace) -> AppConfig:
    config = load_config(args.config)
    return AppConfig(
        tricount_key=args.key or config.tricount_key,
        output_dir=args.output_dir or config.output_dir,
        download_attachments=(
            config.download_attachments
            if args.download_attachments is None
            else args.download_attachments
        ),
        write_excel=config.write_excel if args.write_excel is None else args.write_excel,
        write_sesterce=(
            config.write_sesterce if args.write_sesterce is None else args.write_sesterce
        ),
        save_response=config.save_response if args.save_response is None else args.save_response,
        response_file_name=config.response_file_name,
    )


def export_tricount(settings: AppConfig) -> Path:
    if not settings.tricount_key:
        raise ValueError("A Tricount key is required. Use --key or set tricount_key in config.")

    api = TricountAPI()
    api.authenticate()
    data = api.fetch_tricount_data(settings.tricount_key)

    handler = TricountHandler()
    tricount_title = handler.get_tricount_title(data)
    memberships, transactions = handler.parse_tricount_data(data)

    export_dir = resolve_export_directory(
        settings.output_dir, tricount_title, settings.tricount_key
    )
    export_dir.mkdir(parents=True, exist_ok=True)
    source_url = f"https://tricount.com/{settings.tricount_key}"
    write_tricount_info(export_dir, tricount_title, settings.tricount_key, source_url)

    safe_title = sanitize_path_component(tricount_title)
    csv_path = export_dir / f"Transactions {safe_title}.csv"
    handler.write_to_csv(transactions, file_path=csv_path)

    if settings.write_excel:
        excel_path = export_dir / f"Transactions {safe_title}.xlsx"
        handler.write_to_excel(transactions, file_path=excel_path)

    if settings.write_sesterce:
        sesterce_path = export_dir / f"Transactions {safe_title} (Sesterce).csv"
        handler.write_to_sesterce_csv(memberships, transactions, file_path=sesterce_path)

    if settings.download_attachments:
        attachments_dir = export_dir / f"Attachments {safe_title}"
        handler.download_attachments(transactions, download_folder=attachments_dir)

    if settings.save_response:
        response_path = export_dir / settings.response_file_name
        response_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Raw response saved to {response_path}")

    return export_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)

    try:
        settings = resolve_settings(args)
        output_dir = export_tricount(settings)
    except requests.HTTPError as error:
        print(f"HTTP error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Export completed in {output_dir}")
    return 0
