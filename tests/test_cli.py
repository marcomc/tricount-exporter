from __future__ import annotations

import json
from pathlib import Path

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


def test_main_requires_key_when_not_in_config(capsys) -> None:
    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "A Tricount key is required" in captured.err


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
        ]
    )

    assert exit_code == 0
    assert fake_api.authenticated is True
    assert fake_api.fetched_keys == ["key-123456"]

    export_dir = tmp_path / "City-trip"
    assert export_dir.is_dir()
    assert (export_dir / "Transactions City-trip.csv").is_file()
    assert (export_dir / "Attachments City-trip" / "receipt_1.jpg").is_file()
    assert downloads[0][0] == "https://example.invalid/receipt-1.jpg"

    info = json.loads((export_dir / cli.INFO_FILE_NAME).read_text(encoding="utf-8"))
    assert info["title"] == "City trip"
    assert info["tricount_key"] == "key-123456"
    assert info["source_url"] == "https://tricount.com/key-123456"
    assert "downloaded_at" in info


def test_cli_honors_optional_output_flags(
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
            "--write-excel",
            "--write-sesterce",
            "--save-response",
        ]
    )

    assert exit_code == 0
    export_dir = tmp_path / "City-trip"
    assert (export_dir / "Transactions City-trip.xlsx").is_file()
    assert (export_dir / "Transactions City-trip (Sesterce).csv").is_file()
    assert (export_dir / "response_data.json").is_file()


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
    assert (export_dir / "Transactions City-trip.xlsx").is_file()
    assert (export_dir / "Transactions City-trip (Sesterce).csv").is_file()
    assert (export_dir / "response_data.json").is_file()
    assert not (export_dir / "Attachments City-trip").exists()


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
