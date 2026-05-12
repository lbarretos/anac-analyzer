import pandas as pd
from config import EMPRESA_MAP, ANAC_MIN_YEAR

# O dataset de tarifas é TRIMESTRAL.
# Mapeamentos de colunas (nomes reais do CSV da ANAC podem variar entre versões).
COLS_MAP = {
    "EMPRESA":              "empresa_sigla",
    "EMPRESA (SIGLA)":      "empresa_sigla",
    "ANO":                  "ano",
    "TRIMESTRE":            "trimestre",
    "TRIM":                 "trimestre",
    "ORIGEM":               "origem_icao",
    "AEROPORTO DE ORIGEM":  "origem_icao",
    "DESTINO":              "destino_icao",
    "AEROPORTO DE DESTINO": "destino_icao",
    "TARIFA":               "tarifa_media",
    "TARIFA MÉDIA":         "tarifa_media",
    "TARIFA MEDIA":         "tarifa_media",
    "TARIFA (R$)":          "tarifa_media",
    "ASSENTOS":             "passageiros",
    "PASSAGEIROS":          "passageiros",
}

OUTPUT_COLS = [
    "empresa_sigla", "ano", "trimestre",
    "origem_icao", "destino_icao", "tarifa_media", "passageiros",
]


def transform(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str, decimal=",")
    df.columns = df.columns.str.strip()
    df.rename(columns={k: v for k, v in COLS_MAP.items() if k in df.columns}, inplace=True)

    if "empresa_sigla" not in df.columns:
        raise ValueError(f"Coluna empresa_sigla não encontrada. Colunas disponíveis: {list(df.columns)}")

    df["empresa_sigla"] = (
        df["empresa_sigla"].str.strip().str.upper()
        .map(lambda x: EMPRESA_MAP.get(x, x))
    )

    df["ano"] = pd.to_numeric(df["ano"], errors="coerce").astype("Int16")

    # Trimestre: garantir 1-4
    if "trimestre" in df.columns:
        df["trimestre"] = pd.to_numeric(df["trimestre"], errors="coerce").astype("Int16")
    else:
        # Fallback: se tiver coluna de mês, derivar trimestre
        if "mes" in df.columns:
            df["mes"] = pd.to_numeric(df["mes"], errors="coerce")
            df["trimestre"] = ((df["mes"] - 1) // 3 + 1).astype("Int16")
        else:
            raise ValueError("Nem trimestre nem mes encontrados no CSV de tarifas.")

    df["tarifa_media"] = pd.to_numeric(
        df.get("tarifa_media", pd.Series(dtype=str))
          .astype(str)
          .str.replace(".", "", regex=False)
          .str.replace(",", ".", regex=False),
        errors="coerce",
    )
    df["passageiros"] = pd.to_numeric(df.get("passageiros", pd.Series(dtype=str)), errors="coerce")

    df = df.dropna(subset=["empresa_sigla", "ano", "trimestre"])
    df = df[df["ano"] >= ANAC_MIN_YEAR]
    df = df[df["trimestre"].between(1, 4)]

    for col in ("origem_icao", "destino_icao"):
        if col in df.columns:
            df[col] = df[col].fillna("UNKNOWN").str.strip().replace("", "UNKNOWN")
        else:
            df[col] = "UNKNOWN"

    available = [c for c in OUTPUT_COLS if c in df.columns]
    return df[available].drop_duplicates(
        subset=["empresa_sigla", "ano", "trimestre", "origem_icao", "destino_icao"]
    )
