from __future__ import annotations

import csv
import json
import tomllib
from copy import deepcopy
from pathlib import Path

import openpyxl
import pytest
import requests

from tricount_exporter import cli


class FakeAPI:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.fetched_keys: list[str] = []
        self.authenticated = False

    def authenticate(self) -> None:
        self.authenticated = True

    def fetch_tricount_data(self, tricount_key: str) -> dict:
        self.fetched_keys.append(tricount_key)
        return self.response


def install_fake_api(monkeypatch, response: dict) -> FakeAPI:
    fake_api = FakeAPI(response)
    monkeypatch.setattr(cli, "TricountAPI", lambda: fake_api)
    return fake_api


def fake_download(monkeypatch) -> list[tuple[str, Path]]:
    downloaded: list[tuple[str, Path]] = []

    def _download_file(url: str, file_path: Path) -> None:
        file_path.write_bytes(b"attachment")
        downloaded.append((url, file_path))

    monkeypatch.setattr(cli.TricountHandler, "download_file", staticmethod(_download_file))
    return downloaded


def test_main_prints_help_when_called_without_arguments(capsys) -> None:
    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "usage:" in captured.out
    assert "--key" in captured.out


def test_main_version_prints_cli_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert captured.out.strip() == f"tricount-exporter {cli.__version__}"


def test_package_and_project_versions_are_synchronized() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())

    assert project["project"]["version"] == cli.__version__ == "0.2.0"


def test_cli_exports_csv_attachments_and_metadata(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    fake_api = install_fake_api(monkeypatch, sample_api_response)
    downloads = fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
        ]
    )

    assert exit_code == 0
    assert fake_api.authenticated is True
    assert fake_api.fetched_keys == ["key-123456"]

    export_dir = tmp_path / "City-trip"
    assert export_dir.is_dir()
    assert (export_dir / "transactions-city-trip.csv").is_file()
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "Attachments City-trip" / "receipt_1.jpg").is_file()
    assert downloads[0][0] == "https://example.invalid/receipt-1.jpg"

    with (export_dir / "transactions-city-trip.csv").open(encoding="utf-8", newline="") as handle:
        csv_row = next(csv.DictReader(handle, delimiter=";"))
    assert csv_row["File Names"] == "receipt_1.jpg"

    workbook = openpyxl.load_workbook(export_dir / "transactions-city-trip.xlsx")
    worksheet = workbook["Tricount Transactions"]
    excel_row = dict(
        zip(
            (cell.value for cell in worksheet[1]),
            (cell.value for cell in worksheet[2]),
            strict=True,
        )
    )
    assert excel_row["File Names"] == "receipt_1.jpg"

    info = json.loads((export_dir / cli.INFO_FILE_NAME).read_text(encoding="utf-8"))
    assert info["title"] == "City trip"
    assert info["tricount_key"] == "key-123456"
    assert info["source_url"] == "https://tricount.com/key-123456"
    assert "downloaded_at" in info


def test_attachment_failure_does_not_prevent_transaction_exports(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    install_fake_api(monkeypatch, sample_api_response)

    def fail_download(_url: str, _file_path: Path) -> None:
        raise requests.Timeout("attachment timed out")

    monkeypatch.setattr(cli.TricountHandler, "download_file", staticmethod(fail_download))

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )

    export_dir = tmp_path / "City-trip"
    assert exit_code == 1
    assert (export_dir / "transactions-city-trip.csv").is_file()
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "transactions-city-trip-sesterce.csv").is_file()
    assert (export_dir / "transactions-city-trip.json").is_file()

    with (export_dir / "transactions-city-trip.csv").open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle, delimiter=";"))
    assert row["File Names"] == "receipt_1.jpg"


def test_cli_honors_optional_output_flags_and_preserves_raw_response(
    monkeypatch, sample_rich_api_response: dict, tmp_path: Path
) -> None:
    original_response = deepcopy(sample_rich_api_response)
    install_fake_api(monkeypatch, sample_rich_api_response)
    fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )

    assert exit_code == 0
    export_dir = tmp_path / "City-trip"
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "transactions-city-trip-sesterce.csv").is_file()
    response_path = export_dir / "transactions-city-trip.json"
    assert json.loads(response_path.read_text(encoding="utf-8")) == original_response


def test_cli_dry_run_validates_and_prints_paths_without_writing_files(
    monkeypatch, sample_api_response: dict, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_api = install_fake_api(monkeypatch, sample_api_response)
    downloads = fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
            "--write-sesterce",
            "--save-response",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert fake_api.authenticated is True
    assert fake_api.fetched_keys == ["key-123456"]
    assert "Dry run: validated Tricount key and planned outputs." in captured.out
    assert f"Export directory: {tmp_path / 'City-trip'}" in captured.out
    assert f"CSV: {tmp_path / 'City-trip' / 'transactions-city-trip.csv'}" in captured.out
    assert downloads == []
    assert not (tmp_path / "City-trip").exists()


def test_cli_can_disable_attachments(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    install_fake_api(monkeypatch, sample_api_response)
    fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--no-download-attachments",
        ]
    )

    assert exit_code == 0
    export_dir = tmp_path / "City-trip"
    assert not (export_dir / "Attachments City-trip").exists()


def test_cli_clears_stale_outputs_on_reuse(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    fake_api = install_fake_api(monkeypatch, sample_api_response)
    downloads = fake_download(monkeypatch)

    first_exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )
    assert first_exit_code == 0

    export_dir = tmp_path / "City-trip"
    assert (export_dir / "transactions-city-trip.csv").is_file()
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "transactions-city-trip-sesterce.csv").is_file()
    assert (export_dir / "transactions-city-trip.json").is_file()
    assert (export_dir / "Attachments City-trip" / "receipt_1.jpg").is_file()

    second_exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--no-download-attachments",
        ]
    )

    assert second_exit_code == 0
    assert fake_api.fetched_keys == ["key-123456", "key-123456"]
    assert len(downloads) == 1
    assert (export_dir / "transactions-city-trip.csv").is_file()
    assert not (export_dir / "transactions-city-trip.xlsx").exists()
    assert not (export_dir / "transactions-city-trip-sesterce.csv").exists()
    assert not (export_dir / "transactions-city-trip.json").exists()
    assert not (export_dir / "Attachments City-trip").exists()


def test_cli_removes_legacy_filenames_when_regenerating_exports(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    install_fake_api(monkeypatch, sample_api_response)
    fake_download(monkeypatch)
    export_dir = tmp_path / "City-trip"
    export_dir.mkdir()
    (export_dir / cli.INFO_FILE_NAME).write_text(
        json.dumps({"tricount_key": "key-123456"}), encoding="utf-8"
    )
    legacy_paths = [
        export_dir / "Transactions City-trip.csv",
        export_dir / "Transactions City-trip.xlsx",
        export_dir / "Transactions City-trip (Sesterce).csv",
        export_dir / "response_data.json",
    ]
    for path in legacy_paths:
        path.write_text("legacy", encoding="utf-8")

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )

    assert exit_code == 0
    assert all(not path.exists() for path in legacy_paths)
    assert (export_dir / "transactions-city-trip.csv").is_file()
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "transactions-city-trip-sesterce.csv").is_file()
    assert (export_dir / "transactions-city-trip.json").is_file()


def test_cli_supports_multiple_keys_urls_and_shared_folders(
    monkeypatch, sample_api_response: dict, tmp_path: Path
) -> None:
    fake_api = install_fake_api(monkeypatch, sample_api_response)
    downloads = fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-111111",
            "--key",
            "key-222222",
            "--url",
            "https://tricount.com/share?public_identifier_token=url-key-333333",
            "--url",
            "https://www.tricount.com/url-key-444444",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert fake_api.fetched_keys == [
        "key-111111",
        "key-222222",
        "url-key-333333",
        "url-key-444444",
    ]

    export_dirs = [
        tmp_path / "City-trip",
        tmp_path / "City-trip-222222",
        tmp_path / "City-trip-333333",
        tmp_path / "City-trip-444444",
    ]
    for export_dir in export_dirs:
        assert export_dir.is_dir()
        assert (export_dir / "transactions-city-trip.csv").is_file()
        assert (export_dir / "Attachments City-trip" / "receipt_1.jpg").is_file()

    assert len(downloads) == 4


def test_cli_filters_transactions_by_date_window(
    monkeypatch,
    sample_api_response_two_transactions: dict,
    tmp_path: Path,
) -> None:
    install_fake_api(monkeypatch, sample_api_response_two_transactions)
    downloads = fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--start-date",
            "2026-04-10",
            "--end-date",
            "2026-04-30",
            "--save-response",
        ]
    )

    assert exit_code == 0
    export_dir = tmp_path / "City-trip"
    csv_path = export_dir / "transactions-city-trip.csv"
    assert csv_path.is_file()
    assert not (export_dir / "Attachments City-trip").exists()
    assert downloads == []

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))

    assert rows[0] == [
        "Date",
        "Time",
        "Description",
        "Who Paid",
        "Total",
        "Currency",
        "Local Total",
        "Local Currency",
        "Exchange Rate",
        "Share Giulia",
        "Share Marco",
        "Local Share Giulia",
        "Local Share Marco",
        "Allocation Type Giulia",
        "Allocation Type Marco",
        "Share Ratio Giulia",
        "Share Ratio Marco",
        "Category",
        "Custom Category",
        "Transaction Type",
        "Entry Type",
        "Status",
        "Involved",
        "File Names",
        "Attachment URLs",
        "Transaction ID",
        "Transaction UUID",
        "Created",
        "Updated",
    ]
    assert len(rows) == 2
    assert rows[1][2] == "Museum"
    response_path = export_dir / "transactions-city-trip.json"
    assert (
        json.loads(response_path.read_text(encoding="utf-8"))
        == sample_api_response_two_transactions
    )


def test_csv_exports_preserve_rich_allocations_and_sesterce_fields(
    monkeypatch, sample_rich_api_response: dict, tmp_path: Path
) -> None:
    install_fake_api(monkeypatch, sample_rich_api_response)
    fake_download(monkeypatch)

    exit_code = cli.main(
        [
            "--key",
            "key-123456",
            "--output-dir",
            str(tmp_path),
            "--no-download-attachments",
            "--write-sesterce",
            "--write-excel",
        ]
    )

    assert exit_code == 0
    export_dir = tmp_path / "City-trip"
    with (export_dir / "transactions-city-trip.csv").open(encoding="utf-8", newline="") as handle:
        human_rows = list(csv.DictReader(handle, delimiter=";"))
    with (export_dir / "transactions-city-trip-sesterce.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        sesterce_rows = list(csv.DictReader(handle))

    human_row = human_rows[0]
    assert human_row["Total"] == "36.0"
    assert human_row["Currency"] == "EUR"
    assert human_row["Local Total"] == "30.0"
    assert human_row["Local Currency"] == "GBP"
    assert human_row["Exchange Rate"] == "1.2"
    assert human_row["Share Marco"] == "7.0"
    assert human_row["Share Giulia"] == "29.0"
    assert human_row["Local Share Marco"] == "5.83"
    assert human_row["Local Share Giulia"] == "24.17"
    assert human_row["Allocation Type Marco"] == "AMOUNT"
    assert human_row["Allocation Type Giulia"] == "RATIO"
    assert human_row["Share Ratio Giulia"] == "4"
    assert human_row["Custom Category"] == "Dining 🍔"
    assert human_row["Category"] == "OTHER"
    assert human_row["Transaction Type"] == "NORMAL"
    assert human_row["Entry Type"] == "MANUAL"
    assert human_row["Status"] == "ACTIVE"
    assert human_row["Transaction ID"] == "1001"
    assert human_row["Transaction UUID"] == "11111111-2222-4333-8444-555555555555"
    assert human_row["Created"] == "2026-04-09 18:20:00.000000"
    assert human_row["Updated"] == "2026-04-09 18:31:00.000000"

    workbook = openpyxl.load_workbook(export_dir / "transactions-city-trip.xlsx")
    worksheet = workbook["Tricount Transactions"]
    excel_headers = [cell.value for cell in worksheet[1]]
    assert excel_headers == list(human_row)
    excel_row = dict(zip(excel_headers, (cell.value for cell in worksheet[2]), strict=True))
    assert excel_row["Share Marco"] == 7.0
    assert excel_row["Local Share Giulia"] == 24.17
    assert excel_row["Custom Category"] == "Dining 🍔"
    assert excel_row["Transaction UUID"] == "11111111-2222-4333-8444-555555555555"

    sesterce_row = sesterce_rows[0]
    assert sesterce_row["Paid by Marco"] == "30.0"
    assert sesterce_row["Paid for Marco"] == "5.83"
    assert sesterce_row["Paid for Giulia"] == "24.17"
    assert sesterce_row["Currency"] == "GBP"
    assert sesterce_row["Category"] == "Dining 🍔"
    assert sesterce_row["Exchange rate"] == "1.2"


def test_sesterce_balance_uses_custom_category_or_transfer_fallback(
    sample_rich_api_response: dict,
) -> None:
    memberships, transactions = cli.TricountHandler.parse_tricount_data(sample_rich_api_response)
    members = cli.TricountHandler.member_names(memberships)
    transaction = transactions[0]
    transaction["Transaction Type"] = "BALANCE"

    custom_row = cli.TricountHandler.prepare_sesterce_transaction_data(transaction, members)
    assert custom_row[-2] == "Dining 🍔"

    transaction["Custom Category"] = ""
    fallback_row = cli.TricountHandler.prepare_sesterce_transaction_data(transaction, members)
    assert fallback_row[-2] == "Money Transfer"


@pytest.mark.parametrize(
    ("transaction_type", "local_total", "expected_paid_by", "expected_paid_for"),
    [
        ("NORMAL", 30.0, 30.0, (24.17, 5.83)),
        ("BALANCE", 30.0, 30.0, (24.17, 5.83)),
        ("INCOME", -30.0, -30.0, (-24.17, -5.83)),
    ],
)
def test_sesterce_amounts_preserve_operation_signs_and_balance(
    sample_rich_api_response: dict,
    transaction_type: str,
    local_total: float,
    expected_paid_by: float,
    expected_paid_for: tuple[float, float],
) -> None:
    memberships, transactions = cli.TricountHandler.parse_tricount_data(sample_rich_api_response)
    members = cli.TricountHandler.member_names(memberships)
    transaction = transactions[0]
    transaction["Transaction Type"] = transaction_type
    transaction["Local Total"] = local_total

    row = cli.TricountHandler.prepare_sesterce_transaction_data(transaction, members)
    paid_by = row[2:4]
    paid_for = row[4:6]

    assert paid_by == [0.0, expected_paid_by]
    assert paid_for == list(expected_paid_for)
    assert sum(paid_by) == pytest.approx(sum(paid_for))


def test_parser_falls_back_when_optional_local_amounts_are_null(
    sample_rich_api_response: dict,
) -> None:
    transaction = sample_rich_api_response["Response"][0]["Registry"]["all_registry_entry"][0][
        "RegistryEntry"
    ]
    transaction["amount_local"] = None
    transaction["exchange_rate"] = None
    for allocation in transaction["allocations"]:
        allocation["amount_local"] = None

    _, transactions = cli.TricountHandler.parse_tricount_data(sample_rich_api_response)
    parsed = transactions[0]

    assert parsed["Local Total"] == parsed["Total"] == 36.0
    assert parsed["Local Currency"] == parsed["Currency"] == "EUR"
    assert parsed["Exchange Rate"] == "1"
    assert parsed["Allocations"]["Marco"]["Local Amount"] == 7.0
    assert parsed["Allocations"]["Giulia"]["Local Amount"] == 29.0


def test_parser_rejects_duplicate_participant_display_names(
    sample_api_response: dict,
) -> None:
    memberships = sample_api_response["Response"][0]["Registry"]["memberships"]
    memberships[1]["RegistryMembershipNonUser"]["alias"]["display_name"] = "Marco"

    with pytest.raises(ValueError, match="Duplicate participant display names.*'Marco'"):
        cli.TricountHandler.parse_tricount_data(sample_api_response)


def test_cli_reads_key_from_config(
    monkeypatch, sample_api_response: dict, tmp_path: Path, config_path: Path
) -> None:
    fake_api = install_fake_api(monkeypatch, sample_api_response)
    fake_download(monkeypatch)
    config_path.write_text(
        "\n".join(
            [
                'tricount_key = "config-key"',
                f'output_dir = "{tmp_path}"',
                "download_attachments = false",
                "write_excel = true",
                "write_sesterce = true",
                "save_response = true",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(["--config", str(config_path)])

    assert exit_code == 0
    assert fake_api.fetched_keys == ["config-key"]
    export_dir = tmp_path / "City-trip"
    assert (export_dir / "transactions-city-trip.xlsx").is_file()
    assert (export_dir / "transactions-city-trip-sesterce.csv").is_file()
    assert (export_dir / "transactions-city-trip.json").is_file()
    assert not (export_dir / "Attachments City-trip").exists()


def test_load_config_expands_home_in_output_dir(
    monkeypatch, tmp_path: Path, config_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path.write_text('output_dir = "~/Exports"\n', encoding="utf-8")

    loaded = cli.load_config(config_path)

    assert loaded.output_dir == tmp_path / "Exports"


def test_load_config_supports_multiple_inputs_and_dates(
    config_path: Path,
) -> None:
    config_path.write_text(
        "\n".join(
            [
                'tricount_keys = ["config-key-1", "config-key-2"]',
                'tricount_urls = ["https://tricount.com/config-url-1"]',
                'start_date = "2026-04-01"',
                'end_date = "2026-04-30"',
            ]
        ),
        encoding="utf-8",
    )

    loaded = cli.load_config(config_path)

    assert loaded.tricount_keys == ["config-key-1", "config-key-2"]
    assert loaded.tricount_urls == ["https://tricount.com/config-url-1"]
    assert loaded.start_date is not None
    assert loaded.start_date.isoformat() == "2026-04-01"
    assert loaded.end_date is not None
    assert loaded.end_date.isoformat() == "2026-04-30"


def test_resolve_settings_prefers_cli_flags_over_config(config_path: Path, tmp_path: Path) -> None:
    config_path.write_text(
        "\n".join(
            [
                'tricount_keys = ["config-key"]',
                'output_dir = "/tmp/from-config"',
                "download_attachments = true",
                "write_excel = false",
                "write_sesterce = false",
                "save_response = false",
            ]
        ),
        encoding="utf-8",
    )
    args = cli.build_parser().parse_args(
        [
            "--config",
            str(config_path),
            "--key",
            "cli-key",
            "--output-dir",
            str(tmp_path),
            "--no-download-attachments",
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )

    settings = cli.resolve_settings(args)

    assert settings.tricount_key == "cli-key"
    assert settings.tricount_keys == ["cli-key"]
    assert settings.output_dir == tmp_path
    assert settings.download_attachments is False
    assert settings.write_excel is True
    assert settings.write_sesterce is True
    assert settings.save_response is True


def test_resolve_export_directory_reuses_same_title_for_same_key(tmp_path: Path) -> None:
    export_dir = tmp_path / "City-trip"
    export_dir.mkdir()
    (export_dir / cli.INFO_FILE_NAME).write_text(
        json.dumps({"tricount_key": "same-key"}), encoding="utf-8"
    )

    resolved = cli.resolve_export_directory(tmp_path, "City trip", "same-key")

    assert resolved == export_dir


def test_resolve_export_directory_adds_suffix_for_title_collision(tmp_path: Path) -> None:
    export_dir = tmp_path / "City-trip"
    export_dir.mkdir()
    (export_dir / cli.INFO_FILE_NAME).write_text(
        json.dumps({"tricount_key": "first-key"}), encoding="utf-8"
    )

    resolved = cli.resolve_export_directory(tmp_path, "City trip", "second-key-987654")

    assert resolved == tmp_path / "City-trip-987654"


def test_resolve_export_directory_keeps_searching_when_suffix_is_taken(tmp_path: Path) -> None:
    first_dir = tmp_path / "City-trip"
    first_dir.mkdir()
    (first_dir / cli.INFO_FILE_NAME).write_text(
        json.dumps({"tricount_key": "first-key"}), encoding="utf-8"
    )

    second_dir = tmp_path / "City-trip-987654"
    second_dir.mkdir()
    (second_dir / cli.INFO_FILE_NAME).write_text(
        json.dumps({"tricount_key": "second-key-987654"}), encoding="utf-8"
    )

    resolved = cli.resolve_export_directory(tmp_path, "City trip", "third-key-987654")

    assert resolved == tmp_path / "City-trip-987654-2"


def test_resolve_export_directory_ignores_invalid_metadata_for_reuse(tmp_path: Path) -> None:
    export_dir = tmp_path / "City-trip"
    export_dir.mkdir()
    (export_dir / cli.INFO_FILE_NAME).write_text("{invalid json", encoding="utf-8")

    resolved = cli.resolve_export_directory(tmp_path, "City trip", "key-123456")

    assert resolved == tmp_path / "City-trip-123456"
