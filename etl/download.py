from __future__ import annotations

import os
import requests
from pathlib import Path
from config import ANAC_STATS_URL, ANAC_TARIFAS_URL, ANAC_RAB_URL

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def _download(url: str, dest: Path) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Baixando {dest.name}...")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"  {dest.name}: {size_mb:.1f} MB")
    return dest


def _try_download(url: str, dest: Path) -> Path | None:
    try:
        return _download(url, dest)
    except Exception as e:
        print(f"  AVISO: falha ao baixar {dest.name}: {e}")
        return None


def download_all() -> dict[str, Path | None]:
    return {
        "stats":   _download(ANAC_STATS_URL, RAW_DIR / "Dados_Estatisticos.csv"),
        "tarifas": _try_download(ANAC_TARIFAS_URL, RAW_DIR / "Tarifas_Aereas_Domesticas.csv"),
        "rab":     _download(ANAC_RAB_URL,   RAW_DIR / "RelatorioRAB.csv"),
    }
