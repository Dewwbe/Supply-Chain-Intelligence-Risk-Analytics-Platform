"""A fresh clone has only the Kaggle sources: the pipeline must not require
the hand-supplied UAE Open Data files to download or load the warehouse."""

from __future__ import annotations

import sys

import pandas as pd
from etl.extract import download_raw, uae_open_data
from etl.load import staging


def test_uae_trade_extract_returns_empty_when_not_downloaded(tmp_path):
    assert uae_open_data.run(raw_dir=tmp_path) == {}


def test_uae_trade_extract_reads_the_file_when_present(tmp_path):
    pd.DataFrame({"OBS_VALUE": [1.0]}).to_csv(tmp_path / uae_open_data.FILENAME, index=False)
    assert len(uae_open_data.run(raw_dir=tmp_path)["trade"]) == 1


def test_staging_skips_uae_trade_when_absent(monkeypatch):
    loaded: list[str] = []
    monkeypatch.setattr(staging, "load_olist", lambda f: loaded.append("olist"))
    monkeypatch.setattr(staging, "load_dataco", lambda f: loaded.append("dataco"))
    monkeypatch.setattr(staging, "load_uae_trade", lambda f: loaded.append("uae_trade"))

    staging.load_staging({}, {}, {})
    assert loaded == ["olist", "dataco"]
    staging.load_staging({}, {}, {"trade": pd.DataFrame()})
    assert loaded[-1] == "uae_trade"


def test_download_all_fetches_kaggle_sources_and_skips_url_less_http(monkeypatch):
    fetched: list[str] = []
    monkeypatch.setattr(download_raw, "download_dataset", lambda s: fetched.append(s.name))
    monkeypatch.setattr(sys, "argv", ["download_raw", "--all"])
    download_raw.main()
    assert fetched == ["olist", "dataco"]  # uae_trade/uae_cpi need --url; m5 isn't core


def test_kaggle_credentials_from_env_file_reach_the_cli(monkeypatch):
    settings = download_raw.get_settings()
    monkeypatch.setattr(settings, "kaggle_username", "from-dotenv")
    monkeypatch.setattr(settings, "kaggle_key", "secret")
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_KEY", raising=False)
    assert download_raw._kaggle_env()["KAGGLE_USERNAME"] == "from-dotenv"

    monkeypatch.setenv("KAGGLE_USERNAME", "exported")  # a shell export wins over .env
    assert download_raw._kaggle_env()["KAGGLE_USERNAME"] == "exported"
