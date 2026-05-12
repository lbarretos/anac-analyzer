from __future__ import annotations

import json
import pandas as pd
from datetime import date

# Novo formato (Historico_RAB/YYYY-MM.csv) — primeira linha é "Atualizado em: ..."
COLS_MAP = {
    # Novo formato
    "MARCAS":                       "matricula",
    "NM_FABRICANTE":                "fabricante",
    "DS_MODELO":                    "modelo",
    "NR_ANO_FABRICACAO":            "ano_fabricacao",
    "NR_ASSENTOS":                  "assentos",
    "NR_PMD":                       "mtow_kg",
    "DS_CATEGORIA_HOMOLOGACAO":     "categoria",
    "CF_OPERACIONAL":               "situacao",
    # Formato antigo (RelatorioRAB.csv) — mantido para compatibilidade
    "MARCA":                        "matricula",
    "MATRÍCULA":                    "matricula",
    "MATRICULA":                    "matricula",
    "OPERADOR":                     "operador",
    "NOME DO OPERADOR":             "operador",
    "FABRICANTE":                   "fabricante",
    "MODELO":                       "modelo",
    "ANO FABRICAÇÃO":               "ano_fabricacao",
    "ANO DE FABRICACAO":            "ano_fabricacao",
    "ANO FABRICACAO":               "ano_fabricacao",
    "ASSENTOS":                     "assentos",
    "NR ASSENTOS":                  "assentos",
    "PMTD":                         "mtow_kg",
    "PESO MÁXIMO DE DECOLAGEM":     "mtow_kg",
    "CATEGORIA":                    "categoria",
    "SITUAÇÃO":                     "situacao",
    "SITUACAO":                     "situacao",
}

OUTPUT_COLS = [
    "matricula", "operador", "fabricante", "modelo",
    "ano_fabricacao", "assentos", "mtow_kg", "categoria", "situacao", "snapshot_date",
]


def _extract_operador(raw: str | None) -> str | None:
    """Extrai o nome do primeiro operador do campo JSON do novo formato RAB."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        if parsed and isinstance(parsed, list):
            return str(parsed[0].get("NOME", "")).strip().upper() or None
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return str(raw).strip().upper() or None


def transform(path: str, snapshot_date: date | None = None) -> pd.DataFrame:
    if snapshot_date is None:
        snapshot_date = date.today().replace(day=1)

    # Novo formato tem "Atualizado em: ..." na primeira linha
    with open(path, encoding="utf-8-sig") as f:
        first_line = f.readline().strip()

    skiprows = 1 if first_line.startswith("Atualizado em") else 0

    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str, skiprows=skiprows)
    df.columns = df.columns.str.strip()
    df.rename(columns={k: v for k, v in COLS_MAP.items() if k in df.columns}, inplace=True)

    if "matricula" not in df.columns:
        raise ValueError(f"Coluna matricula não encontrada. Colunas: {list(df.columns)}")

    df["matricula"] = df["matricula"].str.strip().str.upper()

    # Operador: campo direto (formato antigo) ou JSON (novo formato)
    if "operador" in df.columns:
        df["operador"] = df["operador"].str.strip().str.upper()
    elif "OPERADORES" in df.columns:
        df["operador"] = df["OPERADORES"].apply(_extract_operador)
    else:
        df["operador"] = None

    df["ano_fabricacao"] = pd.to_numeric(df.get("ano_fabricacao"), errors="coerce").astype("Int16")
    df["assentos"]       = pd.to_numeric(df.get("assentos"),       errors="coerce").astype("Int16")
    df["mtow_kg"]        = pd.to_numeric(
        df.get("mtow_kg", pd.Series(dtype=str))
          .astype(str)
          .str.replace(".", "", regex=False)
          .str.replace(",", ".", regex=False),
        errors="coerce",
    )

    df["snapshot_date"] = snapshot_date
    df = df.dropna(subset=["matricula"])
    df = df[df["matricula"].str.len() > 0]

    available = [c for c in OUTPUT_COLS if c in df.columns]
    return df[available]
