from __future__ import annotations

import os
from urllib.parse import urlparse
import psycopg2
import psycopg2.extras
import pandas as pd
import requests
from config import DATABASE_URL

_conn: psycopg2.extensions.connection | None = None
_client_mode: str | None = None  # "psycopg2" | "neon_http"

CONFLICT_KEYS: dict[str, list[str]] = {
    "stg_stats":   ["empresa_sigla", "ano", "mes", "natureza", "origem_icao", "destino_icao"],
    "stg_tarifas": ["empresa_sigla", "ano", "trimestre", "origem_icao", "destino_icao"],
    "stg_rab":     ["matricula", "snapshot_date"],
    "dim_empresa": ["sigla_raw"],
}


def _get_neon_http_endpoint() -> str:
    parsed = urlparse(DATABASE_URL)
    host = parsed.hostname or ""
    parts = host.split(".")
    if parts and parts[0].startswith("ep-"):
        parts[0] = "api"
    return f"https://{'.'.join(parts)}/sql"


def _neon_http_headers() -> dict[str, str]:
    return {
        "Neon-Connection-String": DATABASE_URL,
        "Neon-Raw-Text-Output": "true",
        "Neon-Array-Mode": "true",
        "Content-Type": "application/json",
    }


def _query_neon_http(query: str, params: list | None = None, timeout: int = 60) -> dict:
    endpoint = _get_neon_http_endpoint()
    payload = {"query": query, "params": params or []}
    resp = requests.post(endpoint, headers=_neon_http_headers(), json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Neon HTTP error {resp.status_code}: {resp.text}")
    return resp.json()


def get_client() -> psycopg2.extensions.connection | None:
    global _conn, _client_mode
    if _client_mode == "neon_http":
        return None

    if _conn is None or _conn.closed:
        try:
            _conn = psycopg2.connect(
                DATABASE_URL,
                connect_timeout=1,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
            )
            _client_mode = "psycopg2"
        except (psycopg2.OperationalError, Exception) as e:
            print(f"  [DB] Conexão direta TCP falhou ({e}). Ativando modo Neon HTTP (HTTPS:443)...")
            _client_mode = "neon_http"
            return None
    return _conn


def _reconnect() -> psycopg2.extensions.connection | None:
    global _conn
    try:
        if _conn and not _conn.closed:
            _conn.close()
    except Exception:
        pass
    _conn = None
    return get_client()


def upsert_table(df: pd.DataFrame, table: str, chunk_size: int = 500) -> int:
    if df.empty:
        print(f"  [{table}] DataFrame vazio, pulando.")
        return 0

    records = df.astype(object).where(df.notna(), other=None).to_dict(orient="records")
    columns = list(records[0].keys())
    conflict_cols = set(CONFLICT_KEYS[table])

    cols_str = ", ".join(f'"{c}"' for c in columns)
    conflict_str = ", ".join(f'"{c}"' for c in CONFLICT_KEYS[table])
    updates = ", ".join(f'"{c}"=EXCLUDED."{c}"' for c in columns if c not in conflict_cols)

    conn = get_client()

    # Modo 1: Neon HTTP
    if _client_mode == "neon_http" or conn is None:
        total = 0
        http_chunk = min(chunk_size, 1000)
        for i in range(0, len(records), http_chunk):
            chunk = records[i : i + http_chunk]
            placeholders = []
            params = []
            param_idx = 1
            for r in chunk:
                row_ph = []
                for c in columns:
                    row_ph.append(f"${param_idx}")
                    val = r[c]
                    # converter numpy/pandas types para python types nativos para serialização JSON
                    if hasattr(val, "item"):
                        val = val.item()
                    params.append(val)
                    param_idx += 1
                placeholders.append("(" + ", ".join(row_ph) + ")")

            sql = (
                f'INSERT INTO {table} ({cols_str}) VALUES '
                + ", ".join(placeholders)
                + f' ON CONFLICT ({conflict_str}) DO UPDATE SET {updates};'
            )
            _query_neon_http(sql, params)
            total += len(chunk)
            print(f"  [{table}] {total}/{len(records)} rows (via Neon HTTP)", flush=True)
        return total

    # Modo 2: psycopg2 direto
    placeholders = ", ".join(["%s"] * len(columns))
    sql = (
        f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) '
        f'ON CONFLICT ({conflict_str}) DO UPDATE SET {updates}'
    )

    total = 0
    tcp_chunk = 2000
    for i in range(0, len(records), tcp_chunk):
        chunk = records[i : i + tcp_chunk]
        values = [tuple(r[c] for c in columns) for r in chunk]
        for attempt in range(3):
            try:
                c = get_client()
                if c is None:
                    raise psycopg2.OperationalError("Conexão nula")
                with c.cursor() as cur:
                    psycopg2.extras.execute_batch(cur, sql, values, page_size=tcp_chunk)
                c.commit()
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
    period_col = "trimestre" if "tarifas" in table else "mes"
    query = f"SELECT ano, {period_col} FROM {table} ORDER BY ano DESC, {period_col} DESC LIMIT 1;"

    conn = get_client()
    if _client_mode == "neon_http" or conn is None:
        res = _query_neon_http(query)
        rows = res.get("rows", [])
        if rows and rows[0] and rows[0][0] is not None and rows[0][1] is not None:
            return (int(rows[0][0]), int(rows[0][1]))
        return None

    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
    if row and row[0] is not None and row[1] is not None:
        return (int(row[0]), int(row[1]))
    return None


def refresh_materialized_views(conn: psycopg2.extensions.connection | None = None) -> None:
    views = [
        "v_operacional_mensal",
        "v_yield_trimestral",
        "v_frota_ativa",
        "v_utilizacao_frota",
    ]
    c = conn or get_client()
    if _client_mode == "neon_http" or c is None:
        for v in views:
            print(f"  Refreshing {v} (via Neon HTTP)...")
            _query_neon_http(f"REFRESH MATERIALIZED VIEW {v};", timeout=180)
        return

    with c.cursor() as cur:
        for v in views:
            print(f"  Refreshing {v}...")
            cur.execute(f"REFRESH MATERIALIZED VIEW {v}")
    c.commit()
