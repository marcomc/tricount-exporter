from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tomllib
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlparse

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


def parse_optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError(f"Invalid date value: {value!r}. Expected YYYY-MM-DD.") from error
    raise ValueError(f"Invalid date value: {value!r}. Expected YYYY-MM-DD.")


def parse_cli_date(value: str) -> date:
    parsed = parse_optional_date(value)
    if parsed is None:
        raise argparse.ArgumentTypeError("Date must not be empty.")
    return parsed


def coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"Invalid list item: {item!r}")
            stripped = item.strip()
            if stripped:
                result.append(stripped)
        return result
    raise ValueError(f"Invalid list value: {value!r}")


def extract_public_identifier_token_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid Tricount URL: {url!r}")

    host = parsed.netloc.split("@")[-1].split(":")[0].lower()
    if not host.endswith("tricount.com"):
        raise ValueError(f"Expected a tricount.com URL, got {url!r}")

    query = parse_qs(parsed.query)
    for query_key in ("public_identifier_token", "token", "key"):
        values = query.get(query_key)
        if values:
            token = values[0].strip()
            if token:
                return token

    path_segments = [
        unquote(segment).strip() for segment in parsed.path.split("/") if segment.strip()
    ]
    if not path_segments:
        raise ValueError(f"Could not extract a Tricount token from URL: {url!r}")

    return path_segments[-1]


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
    tricount_keys: list[str] = field(default_factory=list)
    tricount_urls: list[str] = field(default_factory=list)
    output_dir: Path = Path.home() / "Downloads"
    start_date: date | None = None
    end_date: date | None = None
    download_attachments: bool = True
    write_excel: bool = False
    write_sesterce: bool = False
    save_response: bool = False
    response_file_name: str = "response_data.json"
    dry_run: bool = False

    @property
    def tricount_key(self) -> str | None:
        return self.tricount_keys[0] if self.tricount_keys else None


@dataclass(frozen=True)
class TricountInput:
    public_identifier_token: str
    source_url: str


@dataclass
class ExportPlan:
    tricount_key: str
    tricount_title: str
    source_url: str
    export_dir: Path
    csv_path: Path
    excel_path: Path | None
    sesterce_path: Path | None
    attachments_dir: Path | None
    response_path: Path | None
    memberships: list[dict[str, str]]
    transactions: list[dict[str, Any]]
    raw_data: dict[str, Any]


@dataclass
class ExportBatchResult:
    export_dirs: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


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
        file_counter = 1
        total_files = sum(len(transaction["Attachments"]) for transaction in transactions)
        print(f"Total attachments: {total_files}")

        if total_files == 0:
            return

        download_folder.mkdir(parents=True, exist_ok=True)

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
    def transaction_date(transaction: dict[str, Any]) -> date:
        return datetime.strptime(transaction["When"], "%Y-%m-%d %H:%M:%S.%f").date()

    @staticmethod
    def filter_transactions_by_date(
        transactions: list[dict[str, Any]],
        start_date: date | None,
        end_date: date | None,
    ) -> list[dict[str, Any]]:
        if start_date is None and end_date is None:
            return transactions

        filtered_transactions: list[dict[str, Any]] = []
        for transaction in transactions:
            transaction_date = TricountHandler.transaction_date(transaction)
            if start_date is not None and transaction_date < start_date:
                continue
            if end_date is not None and transaction_date > end_date:
                continue
            filtered_transactions.append(transaction)
        return filtered_transactions

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

    tricount_keys = coerce_string_list(raw_config.get("tricount_keys"))
    tricount_key = raw_config.get("tricount_key")
    if isinstance(tricount_key, str) and tricount_key.strip():
        tricount_keys.append(tricount_key.strip())

    tricount_urls = coerce_string_list(raw_config.get("tricount_urls"))
    tricount_url = raw_config.get("tricount_url")
    if isinstance(tricount_url, str) and tricount_url.strip():
        tricount_urls.append(tricount_url.strip())

    return AppConfig(
        tricount_keys=tricount_keys,
        tricount_urls=tricount_urls,
        output_dir=Path(raw_config.get("output_dir", "~/Downloads")).expanduser(),
        start_date=parse_optional_date(raw_config.get("start_date")),
        end_date=parse_optional_date(raw_config.get("end_date")),
        download_attachments=parse_bool(
            raw_config.get("download_attachments"), AppConfig.download_attachments
        ),
        write_excel=parse_bool(raw_config.get("write_excel"), AppConfig.write_excel),
        write_sesterce=parse_bool(raw_config.get("write_sesterce"), AppConfig.write_sesterce),
        save_response=parse_bool(raw_config.get("save_response"), AppConfig.save_response),
        response_file_name=raw_config.get("response_file_name", "response_data.json"),
    )


def resolve_tricount_inputs(settings: AppConfig) -> list[TricountInput]:
    sources: list[TricountInput] = []
    for tricount_key in settings.tricount_keys:
        sources.append(
            TricountInput(
                public_identifier_token=tricount_key,
                source_url=f"https://tricount.com/{tricount_key}",
            )
        )
    for tricount_url in settings.tricount_urls:
        sources.append(
            TricountInput(
                public_identifier_token=extract_public_identifier_token_from_url(tricount_url),
                source_url=tricount_url,
            )
        )

    if not sources:
        raise ValueError(
            "At least one Tricount key or URL is required. Use --key or --url,"
            " or set tricount_keys/tricount_urls in config."
        )

    return sources


def build_export_plan(
    settings: AppConfig, api: TricountAPI, tricount_input: TricountInput
) -> ExportPlan:
    data = api.fetch_tricount_data(tricount_input.public_identifier_token)

    handler = TricountHandler()
    tricount_title = handler.get_tricount_title(data)
    memberships, transactions = handler.parse_tricount_data(data)
    transactions = handler.filter_transactions_by_date(
        transactions,
        settings.start_date,
        settings.end_date,
    )

    export_dir = resolve_export_directory(
        settings.output_dir, tricount_title, tricount_input.public_identifier_token
    )
    safe_title = sanitize_path_component(tricount_title)
    source_url = tricount_input.source_url

    return ExportPlan(
        tricount_key=tricount_input.public_identifier_token,
        tricount_title=tricount_title,
        source_url=source_url,
        export_dir=export_dir,
        csv_path=export_dir / f"Transactions {safe_title}.csv",
        excel_path=(
            export_dir / f"Transactions {safe_title}.xlsx" if settings.write_excel else None
        ),
        sesterce_path=(
            export_dir / f"Transactions {safe_title} (Sesterce).csv"
            if settings.write_sesterce
            else None
        ),
        attachments_dir=(
            export_dir / f"Attachments {safe_title}" if settings.download_attachments else None
        ),
        response_path=(
            export_dir / settings.response_file_name if settings.save_response else None
        ),
        memberships=memberships,
        transactions=transactions,
        raw_data=data,
    )


def print_export_plan(plan: ExportPlan) -> None:
    attachment_count = sum(len(transaction["Attachments"]) for transaction in plan.transactions)
    print("Dry run: validated Tricount key and planned outputs.")
    print(f"Title: {plan.tricount_title}")
    print(f"Key: {plan.tricount_key}")
    print(f"Source URL: {plan.source_url}")
    print(f"Transactions: {len(plan.transactions)}")
    print(f"Members: {len(plan.memberships)}")
    print(f"Attachments discovered: {attachment_count}")
    print(f"Export directory: {plan.export_dir}")
    print(f"CSV: {plan.csv_path}")
    if plan.excel_path is not None:
        print(f"Excel: {plan.excel_path}")
    if plan.sesterce_path is not None:
        print(f"Sesterce CSV: {plan.sesterce_path}")
    if plan.attachments_dir is not None:
        print(f"Attachments directory: {plan.attachments_dir}")
    if plan.response_path is not None:
        print(f"Raw response JSON: {plan.response_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download transactions from public Tricount keys or share URLs and export"
            " them to title-based output folders."
        )
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tricount-exporter {__version__}",
    )
    parser.add_argument(
        "--key",
        action="append",
        default=[],
        metavar="KEY",
        help="Public Tricount key. Repeat to export multiple Tricounts.",
    )
    parser.add_argument(
        "--url",
        action="append",
        default=[],
        metavar="URL",
        help="Public Tricount share URL. Repeat to export multiple Tricounts.",
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
    parser.add_argument(
        "--start-date",
        type=parse_cli_date,
        help="Only export transactions on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        type=parse_cli_date,
        help="Only export transactions on or before YYYY-MM-DD.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the key and show planned output paths without writing files.",
    )
    return parser


def resolve_settings(args: argparse.Namespace) -> AppConfig:
    config = load_config(args.config)
    return AppConfig(
        tricount_keys=list(args.key) if args.key else config.tricount_keys,
        tricount_urls=list(args.url) if args.url else config.tricount_urls,
        output_dir=args.output_dir or config.output_dir,
        start_date=args.start_date if args.start_date is not None else config.start_date,
        end_date=args.end_date if args.end_date is not None else config.end_date,
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
        dry_run=args.dry_run,
    )


def export_single_tricount(
    settings: AppConfig, api: TricountAPI, tricount_input: TricountInput
) -> Path:
    plan = build_export_plan(settings, api, tricount_input)

    if settings.dry_run:
        print_export_plan(plan)
        return plan.export_dir

    handler = TricountHandler()
    plan.export_dir.mkdir(parents=True, exist_ok=True)
    write_tricount_info(plan.export_dir, plan.tricount_title, plan.tricount_key, plan.source_url)
    handler.write_to_csv(plan.transactions, file_path=plan.csv_path)

    if plan.excel_path is not None:
        handler.write_to_excel(plan.transactions, file_path=plan.excel_path)

    if plan.sesterce_path is not None:
        handler.write_to_sesterce_csv(
            plan.memberships,
            plan.transactions,
            file_path=plan.sesterce_path,
        )

    if plan.attachments_dir is not None:
        handler.download_attachments(plan.transactions, download_folder=plan.attachments_dir)

    if plan.response_path is not None:
        plan.response_path.write_text(json.dumps(plan.raw_data, indent=2), encoding="utf-8")
        print(f"Raw response saved to {plan.response_path}")

    return plan.export_dir


def export_tricounts(settings: AppConfig) -> ExportBatchResult:
    tricount_inputs = resolve_tricount_inputs(settings)

    api = TricountAPI()
    api.authenticate()

    result = ExportBatchResult()
    for tricount_input in tricount_inputs:
        try:
            output_dir = export_single_tricount(settings, api, tricount_input)
        except Exception as error:  # noqa: BLE001
            result.errors.append(f"{tricount_input.source_url}: {error}")
            print(f"Error exporting {tricount_input.source_url}: {error}", file=sys.stderr)
            continue
        result.export_dirs.append(output_dir)

    return result


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
        result = export_tricounts(settings)
    except requests.HTTPError as error:
        print(f"HTTP error: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if result.errors:
        return 1

    if settings.dry_run:
        if len(result.export_dirs) == 1:
            print(f"Dry run completed for {result.export_dirs[0]}")
        else:
            print(f"Dry run completed for {len(result.export_dirs)} Tricounts.")
        return 0

    if len(result.export_dirs) == 1:
        print(f"Export completed in {result.export_dirs[0]}")
    else:
        print(f"Export completed for {len(result.export_dirs)} Tricounts.")
    return 0
