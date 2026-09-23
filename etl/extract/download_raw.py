"""Phase 1 data acquisition: download raw public datasets into data/raw/.

This is deliberately separate from the per-source *readers* that Phase 2
adds under `etl/extract/` (`olist.py`, `dataco.py`, `m5.py`,
`uae_open_data.py` — see `etl/README.md`): this module only fetches bytes
onto disk; it does not parse or validate anything.

Usage:
    python -m etl.extract.download_raw --list
    python -m etl.extract.download_raw --dataset olist
    python -m etl.extract.download_raw --all          # core Phase 1 datasets only

Requirements:
    - Kaggle datasets (olist, dataco, m5) need the Kaggle CLI configured —
      either `~/.kaggle/kaggle.json` or the `KAGGLE_USERNAME`/`KAGGLE_KEY`
      env vars. See https://www.kaggle.com/docs/api. Nothing here stores or
      reads credentials directly; it shells out to the `kaggle` CLI, which
      owns that.
    - UAE Open Data entries have no URL hard-coded here — the exact
      dataset endpoint on the UAE Open Data Portal / FCSC site must be
      supplied via `--url`, since guessing a government open-data URL is
      worse than asking. Pass it once you have it:
          python -m etl.extract.download_raw --dataset uae_trade --url <url>
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.common.http import ThrottledClient
from src.common.logging import configure_logging, get_logger

logger = get_logger(__name__)

RAW_DIR = Path("data/raw")


@dataclass
class DatasetSource:
    """Where one raw dataset comes from and where it lands."""

    name: str
    kind: str  # "kaggle_dataset" | "kaggle_competition" | "http"
    identifier: str | None  # kaggle slug, competition slug, or URL (http kind)
    dest_subdir: str
    phase1_core: bool  # downloaded by --all; optional ones need --dataset explicitly


# Kaggle slugs are the commonly-cited public identifiers for these exact
# datasets (see docs/data_dictionary.md) — verify against
# https://www.kaggle.com/datasets/<slug> before relying on them; Kaggle
# listings occasionally get renamed or delisted.
REGISTRY: dict[str, DatasetSource] = {
    "olist": DatasetSource(
        name="olist",
        kind="kaggle_dataset",
        identifier="olistbr/brazilian-ecommerce",
        dest_subdir="olist",
        phase1_core=True,
    ),
    "dataco": DatasetSource(
        name="dataco",
        kind="kaggle_dataset",
        identifier="shashwatwork/dataco-smart-supply-chain-for-big-data-analysis",
        dest_subdir="dataco",
        phase1_core=True,
    ),
    "uae_trade": DatasetSource(
        name="uae_trade",
        kind="http",
        identifier=None,  # supply via --url; UAE Open Data Portal, Foreign Trade Volume
        dest_subdir="uae_trade",
        phase1_core=True,
    ),
    "uae_cpi": DatasetSource(
        name="uae_cpi",
        kind="http",
        identifier=None,  # supply via --url; FCSC Consumer Price Index
        dest_subdir="uae_cpi",
        phase1_core=True,
    ),
    "m5": DatasetSource(
        name="m5",
        kind="kaggle_competition",
        identifier="m5-forecasting-accuracy",
        dest_subdir="m5",
        # per docs/implementation_plan.md acquisition order, M5 is pulled once
        # the warehouse exists (Phase 6), not in Phase 1's core batch.
        phase1_core=False,
    ),
}


def _require_kaggle_cli() -> None:
    if shutil.which("kaggle") is None:
        raise RuntimeError(
            "kaggle CLI not found on PATH. Install it (`pip install kaggle`) and "
            "configure credentials at ~/.kaggle/kaggle.json, then retry."
        )


def download_kaggle_dataset(slug: str, dest_dir: Path) -> None:
    """Download and unzip a Kaggle dataset via the `kaggle` CLI."""
    _require_kaggle_cli()
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.info("kaggle_download_start", slug=slug, dest=str(dest_dir))
    subprocess.run(
        ["kaggle", "datasets", "download", "-d", slug, "-p", str(dest_dir), "--unzip"],
        check=True,
    )
    logger.info("kaggle_download_done", slug=slug, dest=str(dest_dir))


def download_kaggle_competition(slug: str, dest_dir: Path) -> None:
    """Download and unzip a Kaggle competition dataset (requires rules acceptance on kaggle.com)."""
    _require_kaggle_cli()
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.info("kaggle_competition_download_start", slug=slug, dest=str(dest_dir))
    subprocess.run(
        ["kaggle", "competitions", "download", "-c", slug, "-p", str(dest_dir)],
        check=True,
    )
    for zip_path in dest_dir.glob("*.zip"):
        shutil.unpack_archive(str(zip_path), str(dest_dir))
    logger.info("kaggle_competition_download_done", slug=slug, dest=str(dest_dir))


def download_http(url: str, dest_dir: Path, filename: str) -> None:
    """Download a single file from a public HTTP(S) endpoint via the throttled client."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename
    client = ThrottledClient()
    try:
        logger.info("http_download_start", url=url, dest=str(dest_path))
        response = client.get(url)
        dest_path.write_bytes(response.content)
        logger.info("http_download_done", url=url, dest=str(dest_path), bytes=len(response.content))
    finally:
        client.close()


def download_dataset(source: DatasetSource, url_override: str | None = None) -> None:
    """Dispatch to the right downloader for one registered dataset."""
    dest_dir = RAW_DIR / source.dest_subdir
    if source.kind == "kaggle_dataset":
        assert source.identifier is not None
        download_kaggle_dataset(source.identifier, dest_dir)
    elif source.kind == "kaggle_competition":
        assert source.identifier is not None
        download_kaggle_competition(source.identifier, dest_dir)
    elif source.kind == "http":
        url = url_override or source.identifier
        if not url:
            raise ValueError(
                f"{source.name} has no URL configured. Re-run with "
                f"--dataset {source.name} --url <uae-open-data-url>."
            )
        download_http(url, dest_dir, filename=f"{source.name}.csv")
    else:
        raise ValueError(f"Unknown source kind: {source.kind}")


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(REGISTRY), help="download a single dataset")
    parser.add_argument("--all", action="store_true", help="download all Phase 1 core datasets")
    parser.add_argument("--url", help="override/supply the source URL (http-kind datasets only)")
    parser.add_argument("--list", action="store_true", help="list registered datasets and exit")
    args = parser.parse_args()

    if args.list:
        for source in REGISTRY.values():
            core = "core" if source.phase1_core else "optional"
            print(f"{source.name:12} {source.kind:20} {core:10} -> data/raw/{source.dest_subdir}")
        return

    if args.dataset:
        download_dataset(REGISTRY[args.dataset], url_override=args.url)
    elif args.all:
        for source in REGISTRY.values():
            if source.phase1_core:
                download_dataset(source)
    else:
        parser.error("pass --dataset <name>, --all, or --list")


if __name__ == "__main__":
    main()
