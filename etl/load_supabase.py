from __future__ import annotations

import psycopg2
import psycopg2.extras
import pandas as pd
from config import DATABASE_URL

_conn: psycopg2.extensions.connection | None = None

CONFLICT_KEYS: dict[str, list[str]] = {
    "stg_stats":   ["empresa_sigla", "ano", "mes", "natureza", "origem_icao", "destino_icao"],
    "stg_tarifas": ["empresa_sigla", "ano", "trimestre", "origem_icao", "destino_icao"],
    "stg_rab":     ["matricula", "snapshot_date"],
    "dim_empresa": ["sigla_raw"],
}


def get_client() -> psycopg2.extensions.connection:
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(DATABASE_URL, keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    return _conn


def _reconnect() -> psycopg2.extensions.connection:
    global _conn
    try:
        if _conn and not _conn.closed:
            _conn.close()
    except Exception:
        pass
    _conn = None
    return get_client()


def upsert_table(df: pd.DataFrame, table: str, chunk_size: int = 2000) -> int:
    if df.empty:
        print(f"  [{table}] DataFrame vazio, pulando.")
        return 0

    # Converte para object dtype antes de substituir NA/NaN por None,
    # evitando que colunas float64 revertam None para NaN.
    records = df.astype(object).where(df.notna(), other=None).to_dict(orient="records")
    columns = list(records[0].keys())
    conflict_cols = set(CONFLICT_KEYS[table])

    cols_str = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    conflict_str = ", ".join(f'"{c}"' for c in CONFLICT_KEYS[table])
    updates = ", ".join(f'"{c}"=EXCLUDED."{c}"' for c in columns if c not in conflict_cols)

    sql = (
        f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_str}) DO UPDATE SET {updates}'
    )

    total = 0
    for i in range(0, len(records), chunk_size):
        chunk = records[i : i + chunk_size]
        values = [tuple(r[c] for c in columns) for r in chunk]
        for attempt in range(3):
            try:
                conn = get_client()
                with conn.cursor() as cur:
                    # execute_batch sends all rows in a single network round-trip
                    psycopg2.extras.execute_batch(cur, sql, values, page_size=chunk_size)
                conn.commit()
                break
            except psycopg2.OperationalError:
                if attempt == 2:
                    raise
                print(f"  [{table}] Conexão perdida, reconectando...")
                _reconnect()
        total += len(chunk)
        print(f"  [{table}] {total}/{len(records)} rows", flush=True)
    return total


def get_max_periodo(table: str) -> tuple[int, int] | None:
    conn = get_client()
    with conn.cursor() as cur:
        cur.execute(f"SELECT ano, mes FROM {table} ORDER BY ano DESC, mes DESC LIMIT 1")
        row = cur.fetchone()
    if row:
        return (int(row[0]), int(row[1]))
    return None


def refresh_materialized_views(conn: psycopg2.extensions.connection | None = None) -> None:
    c = conn or get_client()
    views = [
        "v_operacional_mensal",
        "v_yield_trimestral",
        "v_frota_ativa",
        "v_utilizacao_frota",
    ]
    with c.cursor() as cur:
        for v in views:
            print(f"  Refreshing {v}...")
            cur.execute(f"REFRESH MATERIALIZED VIEW {v}")
    c.commit()
