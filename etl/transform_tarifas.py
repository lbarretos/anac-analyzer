from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
from config import EMPRESA_MAP, ANAC_MIN_YEAR, ANAC_TARIFAS_BASE_URL, SAS_HEADERS

CANONICAL = {
    "ano": ["ANO", "NR_ANO_REFERENCIA", "ANO DE REFERÊNCIA", "ANO DE REFERENCIA"],
    "mes": ["MES", "MÊS", "NR_MES_REFERENCIA", "MÊS DE REFERÊNCIA", "MES DE REFERENCIA"],
    "trimestre": ["TRIMESTRE", "TRIM"],
    "empresa_sigla": [
        "EMPRESA", "EMPRESA (SIGLA)", "SG_EMPRESA_ICAO",
        "ICAO EMPRESA AÉREA", "ICAO EMPRESA AEREA",
    ],
    "origem_icao": [
        "ORIGEM", "AEROPORTO DE ORIGEM", "SG_ICAO_ORIGEM",
        "ICAO AERÓDROMO ORIGEM", "ICAO AERODROMO ORIGEM",
    ],
    "destino_icao": [
        "DESTINO", "AEROPORTO DE DESTINO", "SG_ICAO_DESTINO",
        "ICAO AERÓDROMO DESTINO", "ICAO AERODROMO DESTINO",
    ],
    "tarifa": [
        "TARIFA", "NR_TARIFA", "TARIFA-N", "TARIFA MÉDIA",
        "TARIFA MEDIA", "TARIFA (R$)",
    ],
    "assentos": [
        "ASSENTOS", "NR_ASSENTOS", "ASSENTOS COMERCIALIZADOS",
        "PASSAGEIROS",
    ],
}

OUTPUT_COLS = [
    "empresa_sigla", "ano", "trimestre",
    "origem_icao", "destino_icao", "tarifa_media", "passageiros",
]


def clean_fare_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    cols_upper = {str(c).strip().upper(): c for c in df.columns}

    # Resolver colunas canônicas
    resolved: dict[str, str | None] = {}
    for target, candidates in CANONICAL.items():
        resolved[target] = next((cols_upper[c] for c in candidates if c in cols_upper), None)

    if not resolved["empresa_sigla"] or not resolved["ano"]:
        raise ValueError(f"Colunas mínimas não encontradas. Colunas: {list(df.columns)}")

    # Extrair e tipar
    ano = pd.to_numeric(df[resolved["ano"]], errors="coerce")

    # Trimestre: direto ou derivado de mês
    if resolved["trimestre"]:
        trimestre = pd.to_numeric(df[resolved["trimestre"]], errors="coerce")
    elif resolved["mes"]:
        mes = pd.to_numeric(df[resolved["mes"]], errors="coerce")
        trimestre = (mes - 1) // 3 + 1
    else:
        raise ValueError("Nem trimestre nem mes encontrados no CSV de tarifas.")

    empresa = (
        df[resolved["empresa_sigla"]].astype(str).str.strip().str.upper()
        .map(lambda x: EMPRESA_MAP.get(x, x))
    )

    origem = (
        df[resolved["origem_icao"]].fillna("UNKNOWN").astype(str).str.strip().str.upper().replace("", "UNKNOWN")
        if resolved["origem_icao"] else pd.Series("UNKNOWN", index=df.index)
    )

    destino = (
        df[resolved["destino_icao"]].fillna("UNKNOWN").astype(str).str.strip().str.upper().replace("", "UNKNOWN")
        if resolved["destino_icao"] else pd.Series("UNKNOWN", index=df.index)
    )

    tarifa_raw = df[resolved["tarifa"]] if resolved["tarifa"] else pd.Series(0, index=df.index)
    raw_str = tarifa_raw.astype(str).str.strip()
    has_comma = raw_str.str.contains(",", na=False)
    res_comma = raw_str.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    tarifa_normalized = raw_str.where(~has_comma, res_comma)
    tarifa = pd.to_numeric(tarifa_normalized, errors="coerce")

    assentos_raw = df[resolved["assentos"]] if resolved["assentos"] else pd.Series(0, index=df.index)
    assentos = pd.to_numeric(assentos_raw, errors="coerce")

    clean = pd.DataFrame({
        "empresa_sigla": empresa,
        "ano":           ano,
        "trimestre":     trimestre,
        "origem_icao":   origem,
        "destino_icao":  destino,
        "tarifa":        tarifa,
        "passageiros":   assentos,
        "receita":       tarifa * assentos,
    })

    # Filtros de consistência
    clean = clean.dropna(subset=["empresa_sigla", "ano", "trimestre", "tarifa", "passageiros"])
    clean = clean[clean["ano"] >= ANAC_MIN_YEAR]
    clean = clean[clean["trimestre"].between(1, 4)]
    clean = clean[clean["passageiros"] > 0]

    if clean.empty:
        return pd.DataFrame(columns=OUTPUT_COLS)

    # Agregar para o nível (empresa, ano, trimestre, origem, destino)
    agg = clean.groupby(
        ["empresa_sigla", "ano", "trimestre", "origem_icao", "destino_icao"],
        as_index=False,
    ).agg(
        receita=("receita", "sum"),
        passageiros=("passageiros", "sum"),
    )

    agg = agg.copy()
    agg["tarifa_media"] = (agg["receita"] / agg["passageiros"]).round(2)
    agg["ano"] = agg["ano"].astype("int16")
    agg["trimestre"] = agg["trimestre"].astype("int16")
    agg["passageiros"] = agg["passageiros"].astype("int64")

    return agg[OUTPUT_COLS]


def transform(path: str) -> pd.DataFrame:
    """Processa arquivo local de tarifas (mantido para testes e compatibilidade)."""
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str)
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="latin1", dtype=str)
    return clean_fare_df(df)


def fetch_month(year: int, month: int, session: requests.Session | None = None) -> pd.DataFrame | None:
    """Baixa e processa um mês de tarifas diretamente do SAS da ANAC."""
    url = f"{ANAC_TARIFAS_BASE_URL}{year}/{year}{month:02d}.csv"
    getter = session.get if session else requests.get
    try:
        resp = getter(url, headers=SAS_HEADERS, timeout=30)
        if resp.status_code != 200:
            return None
        content = resp.content
        if len(content) < 500 and b"<html" in content.lower():
            # Página de bloqueio/erro
            return None
        df = pd.read_csv(io.BytesIO(content), sep=";", encoding="latin1", dtype=str)
        return clean_fare_df(df)
    except Exception as e:
        print(f"    [Tarifas] Erro ao baixar/processar {year}-{month:02d}: {e}")
        return None


def process_year(year: int, max_workers: int = 4) -> pd.DataFrame:
    """Baixa todos os meses do ano em paralelo e consolida por rota/trimestre."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_month, year, m) for m in range(1, 13)]
        results = [f.result() for f in futures]

    valid = [r for r in results if r is not None and not r.empty]
    if not valid:
        return pd.DataFrame(columns=OUTPUT_COLS)

    combined = pd.concat(valid, ignore_index=True)
    # Re-agrupar caso haja o mesmo par de rotas em múltiplos meses do mesmo trimestre
    combined = combined.copy()
    combined["receita"] = combined["tarifa_media"] * combined["passageiros"]
    agg = combined.groupby(
        ["empresa_sigla", "ano", "trimestre", "origem_icao", "destino_icao"],
        as_index=False,
    ).agg(
        receita=("receita", "sum"),
        passageiros=("passageiros", "sum"),
    ).copy()
    agg["tarifa_media"] = (agg["receita"] / agg["passageiros"]).round(2)
    agg["ano"] = agg["ano"].astype("int16")
    agg["trimestre"] = agg["trimestre"].astype("int16")
    agg["passageiros"] = agg["passageiros"].astype("int64")

    return agg[OUTPUT_COLS]
