import pandas as pd
from config import EMPRESA_MAP, ANAC_MIN_YEAR

COLS_MAP = {
    # Novo formato (2025+) — underscores, compartilhado com antigo onde igual
    "EMPRESA_SIGLA":                "empresa_sigla",
    "EMPRESA_NOME":                 "empresa_nome",
    "ANO":                          "ano",
    "MES":                          "mes",
    "NATUREZA":                     "natureza",
    "AEROPORTO_DE_ORIGEM_SIGLA":    "origem_icao",
    "AEROPORTO_DE_DESTINO_SIGLA":   "destino_icao",
    "PASSAGEIROS_PAGOS":            "passageiros_pagos",
    "PASSAGEIROS_GRATIS":           "passageiros_gratis",
    "ASSENTOS":                     "assentos_disponibilizados",
    "DECOLAGENS":                   "decolagens",
    "CARGA_PAGA_KG":                "carga_kg",
    "CORREIO_KG":                   "correio_kg",
    "DISTANCIA_VOADA_KM":           "distancia_km",
    "COMBUSTIVEL_LITROS":           "combustivel_litros",
    # Formato antigo (espaços e acentos)
    "EMPRESA":                      "empresa_sigla",
    "EMPRESA (SIGLA)":              "empresa_sigla",
    "EMPRESA (Nome)":               "empresa_nome",
    "MÊS":                          "mes",
    "AEROPORTO DE ORIGEM":          "origem_icao",
    "AEROPORTO DE DESTINO":         "destino_icao",
    "PASSAGEIROS PAGOS":            "passageiros_pagos",
    "PASSAGEIROS GRÁTIS":           "passageiros_gratis",
    "PASSAGEIROS GRATIS":           "passageiros_gratis",
    "ASSENTOS COMERCIALIZADOS":     "assentos_disponibilizados",
    "CARGA PAGA (KG)":              "carga_kg",
    "CORREIO (KG)":                 "correio_kg",
    "DISTÂNCIA VOADA (KM)":         "distancia_km",
    "DISTANCIA VOADA (KM)":         "distancia_km",
    "COMBUSTÍVEL (LITROS)":         "combustivel_litros",
    "COMBUSTIVEL (LITROS)":         "combustivel_litros",
}

NUMERIC_COLS = [
    "passageiros_pagos", "passageiros_gratis",
    "assentos_disponibilizados", "decolagens",
    "carga_kg", "correio_kg", "distancia_km", "combustivel_litros",
]

OUTPUT_COLS = [
    "empresa_sigla", "empresa_nome", "ano", "mes", "natureza",
    "origem_icao", "destino_icao", "passageiros_pagos", "passageiros_gratis",
    "assentos_disponibilizados", "decolagens", "carga_kg", "correio_kg",
    "distancia_km", "combustivel_litros",
]


def _clean_chunk(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    df.rename(columns={k: v for k, v in COLS_MAP.items() if k in df.columns}, inplace=True)

    if "empresa_sigla" not in df.columns:
        return pd.DataFrame(columns=OUTPUT_COLS)

    df["empresa_sigla"] = (
        df["empresa_sigla"].str.strip().str.upper()
        .map(lambda x: EMPRESA_MAP.get(x, x))
    )

    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                       .str.replace(".", "", regex=False)
                       .str.replace(",", ".", regex=False),
                errors="coerce",
            )

    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int16")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int16")
    df = df.dropna(subset=["empresa_sigla", "ano", "mes"])
    df = df[df["ano"] >= ANAC_MIN_YEAR]

    # Sentinel para colunas de UNIQUE key que podem ser nulas
    for col in ("origem_icao", "destino_icao"):
        if col in df.columns:
            df[col] = df[col].fillna("UNKNOWN").str.strip().replace("", "UNKNOWN")

    available = [c for c in OUTPUT_COLS if c in df.columns]
    return df[available]


def transform(path: str) -> pd.DataFrame:
    # Novo formato tem "Atualizado em: ..." na primeira linha
    with open(path, encoding="utf-8-sig") as f:
        first_line = f.readline().strip()
    skiprows = 1 if first_line.startswith("Atualizado em") else 0

    chunks = []
    for chunk in pd.read_csv(
        path, sep=";", encoding="utf-8-sig", dtype=str, decimal=",",
        chunksize=100_000, skiprows=skiprows,
    ):
        cleaned = _clean_chunk(chunk)
        if not cleaned.empty:
            chunks.append(cleaned)

    if not chunks:
        return pd.DataFrame(columns=OUTPUT_COLS)
    return pd.concat(chunks, ignore_index=True)
