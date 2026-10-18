#!/usr/bin/env python3
"""
ANAC Aviation Analytics — MCP Server (Model Context Protocol).

Fornece acesso analítico de somente-leitura ao banco de dados da ANAC (Neon PostgreSQL):
  - Consulta ad-hoc via SQL seguro (query)
  - Descoberta de catálogo e schema (list_tables, describe_table)
  - Resolução de companhias aéreas (resolve_airline)
  - Métricas de Yield e PRASK (get_yield_metrics)
  - Dimensionamento e idade de frota (get_fleet_metrics)
  - Utilização de frota por aeronave (get_fleet_utilization)
  - Volume e tráfego operacional mensal (get_traffic_volume)
  - Diagnóstico de integridade da base (check_data_integrity)

Transporte:
  - Padrão: stdio (Claude Code, Claude Desktop, Antigravity, Cursor)
  - Opcional: HTTP (Streamable HTTP) via --http --port <porta>

Uso:
  .venv/bin/python scripts/mcp/anac_mcp.py
  .venv/bin/python scripts/mcp/anac_mcp.py --http --port 8766
"""
from __future__ import annotations

import argparse
import decimal
import json
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------- Configuração de Ambiente ----------
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não configurada no .env", file=sys.stderr)
    sys.exit(1)

MAX_ROWS = 500
MAX_CELL_CHARS = 10_000
MAX_RESPONSE_CHARS = 30_000
QUERY_TIMEOUT_MS = 20_000

mcp = FastMCP("anac-analyzer", stateless_http=True)

# Filtro de segurança SQL para modo somente-leitura
_LITERAIS = re.compile(
    r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|`[^`]*`|\[[^\]]*\]|--[^\n]*|/\*.*?(?:\*/|$)",
    re.S,
)
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXECUTE|GRANT|REVOKE|VACUUM|REINDEX|SET|RESET|CALL|DO)\b"
    r"|\bINTO\b",
    re.I,
)


def get_db():
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = {QUERY_TIMEOUT_MS};")
        cur.execute("SET default_transaction_read_only = TRUE;")
    conn.commit()
    return conn


def _cortar_para(v, n: int):
    if isinstance(v, str) and len(v) > n:
        return v[:n] + f"…[truncado: {len(v)} chars]"
    return v


def _serializar(val):
    if isinstance(val, (decimal.Decimal, float)):
        return float(val)
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _tabular(colunas: list[str], linhas: list[list], aviso: str | None = None) -> dict:
    total = len(linhas)
    usados = len(json.dumps(colunas, ensure_ascii=False))
    mantidas = []

    for l in linhas:
        l_serialized = [_serializar(c) for c in l]
        n = len(json.dumps(l_serialized, ensure_ascii=False, default=str))
        if mantidas and usados + n > MAX_RESPONSE_CHARS:
            break
        if not mantidas and n > MAX_RESPONSE_CHARS:
            l_serialized = [_cortar_para(str(v), max(200, MAX_RESPONSE_CHARS // max(len(l), 1))) for v in l_serialized]
            n = len(json.dumps(l_serialized, ensure_ascii=False, default=str))
        mantidas.append(l_serialized)
        usados += n

    out = {"colunas": colunas, "linhas": mantidas}
    avisos = [aviso] if aviso else []
    if len(mantidas) < total:
        avisos.append(
            f"Resposta truncada em {len(mantidas)} de {total} linhas para caber no limite de "
            f"{MAX_RESPONSE_CHARS} caracteres. Use LIMIT ou filtros mais específicos."
        )
    if avisos:
        out["aviso"] = "; ".join(avisos)
    return out


# ---------- Ferramentas MCP ----------

@mcp.tool()
def list_tables() -> dict:
    """Lista todas as tabelas staging e views materializadas analíticas do banco ANAC com contagens de linhas."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    table_name,
                    'TABLE' AS tipo,
                    CASE table_name
                        WHEN 'dim_empresa' THEN 'Normalização e cadastro de companhias aéreas (sigla raw, sigla atual, razão social)'
                        WHEN 'stg_stats' THEN 'Dados Estatísticos do Transporte Aéreo (etapas de voo, pax, decolagens, carga, ASK, RPK)'
                        WHEN 'stg_tarifas' THEN 'Tarifas Aéreas Domésticas agregadas por rota e trimestre (tarifa média ponderada, pax)'
                        WHEN 'stg_rab' THEN 'Registro Aeronáutico Brasileiro (aeronaves ativas, fabricante, modelo, assentos, operador)'
                        ELSE 'Tabela'
                    END AS descricao
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                UNION ALL
                SELECT
                    matviewname AS table_name,
                    'MATERIALIZED VIEW' AS tipo,
                    CASE matviewname
                        WHEN 'v_operacional_mensal' THEN 'Consolidação mensal de pax, assentos, decolagens, rpk, ask e load factor por empresa'
                        WHEN 'v_yield_trimestral' THEN 'Yield nominal (R$/RPK), PRASK (R$/ASK), receita proxy e load factor trimestral'
                        WHEN 'v_frota_ativa' THEN 'Frota comercial ativa mais recente via RAB (aeronaves ativas, idade média, assentos médios)'
                        WHEN 'v_utilizacao_frota' THEN 'Utilização de frota: ASK por aeronave, ciclos/aeronave e ASK/decolagem por mês'
                        ELSE 'View Materializada'
                    END AS descricao
                FROM pg_matviews
                WHERE schemaname = 'public'
                ORDER BY tipo, table_name;
            """)
            rows = cur.fetchall()
            resultado = []
            for name, tipo, desc in rows:
                try:
                    cur.execute(f"SELECT count(*) FROM {name};")
                    cnt = cur.fetchone()[0]
                except Exception:
                    cnt = None
                resultado.append({
                    "nome": name,
                    "tipo": tipo,
                    "linhas": cnt,
                    "descricao": desc,
                })
            return {"tabelas": resultado}
    finally:
        conn.close()


@mcp.tool()
def describe_table(table_name: str) -> dict:
    """Retorna o esquema detalhado (colunas, tipos de dados, nulos e valores de amostra) de uma tabela ou view.

    Args:
        table_name: Nome da tabela ou view (ex: 'v_yield_trimestral', 'v_frota_ativa', 'stg_stats', 'dim_empresa')
    """
    clean_name = table_name.strip().lower()
    if not re.match(r"^[a-z0-9_]+$", clean_name):
        return {"erro": f"Nome de tabela inválido: '{table_name}'"}

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (clean_name,))
            cols = cur.fetchall()
            if not cols:
                # Pode ser materialized view
                cur.execute("""
                    SELECT a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull
                    FROM pg_attribute a
                    JOIN pg_class c ON a.attrelid = c.oid
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    WHERE c.relname = %s AND n.nspname = 'public' AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY a.attnum;
                """, (clean_name,))
                cols = cur.fetchall()

            if not cols:
                return {"erro": f"Tabela ou view '{clean_name}' não encontrada."}

            col_defs = [{"coluna": c[0], "tipo": c[1], "anulavel": c[2]} for c in cols]

            # Obter amostra
            cur.execute(f"SELECT * FROM {clean_name} LIMIT 3;")
            sample_rows = cur.fetchall()
            sample_data = [[_serializar(val) for val in r] for r in sample_rows]

            return {
                "tabela": clean_name,
                "colunas": col_defs,
                "amostra": sample_data,
            }
    finally:
        conn.close()


@mcp.tool()
def resolve_airline(query: str) -> dict:
    """Busca companhias aéreas na tabela de dimensão dim_empresa por sigla, ICAO, nome comercial ou razão social.

    Args:
        query: Termo de busca (ex: 'Gol', 'GLO', 'LATAM', 'TAM', 'Azul', 'Passaredo', 'VoePass')
    """
    termo = f"%{query.strip()}%"
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT
                    sigla_atual,
                    nome_comercial,
                    icao,
                    razao_social,
                    ativa,
                    string_agg(DISTINCT sigla_raw, ', ') AS siglas_raw_mapeadas
                FROM dim_empresa
                WHERE sigla_raw ILIKE %s
                   OR sigla_atual ILIKE %s
                   OR nome_comercial ILIKE %s
                   OR icao ILIKE %s
                   OR razao_social ILIKE %s
                GROUP BY sigla_atual, nome_comercial, icao, razao_social, ativa
                ORDER BY ativa DESC, sigla_atual;
            """, (termo, termo, termo, termo, termo))
            rows = cur.fetchall()
            encontradas = [
                {
                    "sigla_atual": r[0],
                    "nome_comercial": r[1],
                    "icao": r[2],
                    "razao_social_rab": r[3],
                    "ativa": r[4],
                    "siglas_raw": r[5],
                }
                for r in rows
            ]
            return {
                "termo": query,
                "total": len(encontradas),
                "empresas": encontradas,
            }
    finally:
        conn.close()


@mcp.tool()
def query(sql: str) -> dict:
    """Executa um comando SQL SELECT de somente-leitura no banco de dados ANAC (Neon PostgreSQL).

    Permite responder a qualquer pergunta analítica complexa com agrupamentos, filtros e joins.
    Retorna resultado tabular {colunas, linhas}. Máximo de 500 linhas.
    Comandos de escrita, modificação ou destruição são expressamente bloqueados.

    Args:
        sql: Comando SQL SELECT (ex: 'SELECT sigla_atual, ano, sum(pax_pagos) FROM v_operacional_mensal GROUP BY 1, 2 ORDER BY 2 DESC;')
    """
    texto_sem_literais = _LITERAIS.sub(" ", sql).strip()
    if not texto_sem_literais.upper().startswith("SELECT") and not texto_sem_literais.upper().startswith("WITH"):
        return {"erro": "Apenas consultas SELECT ou WITH ... SELECT são permitidas neste servidor MCP."}

    m = _FORBIDDEN.search(texto_sem_literais)
    if m:
        return {"erro": f"Operação SQL não permitida detectada: '{m.group(0)}'. Somente leitura."}

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return {"colunas": [], "linhas": []}
            colunas = [d[0] for d in cur.description]
            linhas = cur.fetchmany(MAX_ROWS + 1)
            aviso = None
            if len(linhas) > MAX_ROWS:
                aviso = f"Limite de {MAX_ROWS} linhas atingido. Restrinja a consulta com WHERE ou LIMIT."
                linhas = linhas[:MAX_ROWS]
            return _tabular(colunas, [list(r) for r in linhas], aviso)
    except Exception as e:
        return {"erro": str(e)}
    finally:
        conn.close()


@mcp.tool()
def get_yield_metrics(
    empresa: str | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    trimestre: int | None = None,
) -> dict:
    """Retorna métricas financeiras/operacionais trimestrais de Yield (R$/RPK), PRASK (R$/ASK), receita proxy e passageiros.

    Args:
        empresa: Sigla canônica da empresa (ex: 'LATAM', 'GOL', 'AZUL', 'VOEPASS'). Se omitido, retorna todas.
        ano_inicio: Ano inicial do filtro (ex: 2022)
        ano_fim: Ano final do filtro (ex: 2024)
        trimestre: Trimestre de 1 a 4. Se omitido, retorna todos.
    """
    conds = ["1=1"]
    params = []
    if empresa:
        conds.append("sigla_atual = %s")
        params.append(empresa.strip().upper())
    if ano_inicio:
        conds.append("ano >= %s")
        params.append(ano_inicio)
    if ano_fim:
        conds.append("ano <= %s")
        params.append(ano_fim)
    if trimestre:
        conds.append("trimestre = %s")
        params.append(trimestre)

    sql = f"""
        SELECT
            sigla_atual,
            nome_comercial,
            ano,
            trimestre,
            pax_pagos,
            round(load_factor::numeric, 4) AS load_factor,
            round(yield_nominal::numeric, 4) AS yield_nominal_reais_rpk,
            round(prask::numeric, 4) AS prask_reais_ask,
            round(receita_proxy::numeric, 2) AS receita_proxy_reais,
            pax_tarifas,
            rpk,
            ask
        FROM v_yield_trimestral
        WHERE {" AND ".join(conds)}
        ORDER BY ano DESC, trimestre DESC, sigla_atual;
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            return _tabular(colunas, [list(r) for r in linhas])
    finally:
        conn.close()


@mcp.tool()
def get_fleet_metrics(empresa: str | None = None) -> dict:
    """Retorna dados da frota comercial ativa (RBAC 121 / 135) do snapshot mais recente do RAB: número de aeronaves, idade média, assentos médios e modelos operados.

    Args:
        empresa: Sigla canônica da empresa (ex: 'LATAM', 'GOL', 'AZUL', 'VOEPASS', 'MAP'). Se omitido, retorna todas.
    """
    conds = ["1=1"]
    params = []
    if empresa:
        conds.append("sigla_atual = %s")
        params.append(empresa.strip().upper())

    sql = f"""
        SELECT
            sigla_atual,
            nome_comercial,
            aeronaves_ativas,
            idade_media,
            assentos_medios,
            modelos
        FROM v_frota_ativa
        WHERE {" AND ".join(conds)}
        ORDER BY aeronaves_ativas DESC;
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            return _tabular(colunas, [list(r) for r in linhas])
    finally:
        conn.close()


@mcp.tool()
def get_fleet_utilization(
    empresa: str | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
) -> dict:
    """Retorna indicadores mensais de produtividade e utilização da frota: ASK por aeronave, ciclos/decolagens por aeronave, e ASK por decolagem.

    Args:
        empresa: Sigla canônica da empresa (ex: 'LATAM', 'GOL', 'AZUL'). Se omitido, retorna todas.
        ano_inicio: Ano inicial (ex: 2024)
        ano_fim: Ano final (ex: 2026)
    """
    conds = ["1=1"]
    params = []
    if empresa:
        conds.append("sigla_atual = %s")
        params.append(empresa.strip().upper())
    if ano_inicio:
        conds.append("ano >= %s")
        params.append(ano_inicio)
    if ano_fim:
        conds.append("ano <= %s")
        params.append(ano_fim)

    sql = f"""
        SELECT
            sigla_atual,
            nome_comercial,
            periodo,
            ano,
            mes,
            aeronaves_ativas,
            ask_por_aeronave,
            ciclos_por_aeronave,
            ask_por_decolagem,
            round(load_factor::numeric, 4) AS load_factor,
            decolagens
        FROM v_utilizacao_frota
        WHERE {" AND ".join(conds)}
        ORDER BY ano DESC, mes DESC, sigla_atual;
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            return _tabular(colunas, [list(r) for r in linhas])
    finally:
        conn.close()


@mcp.tool()
def get_traffic_volume(
    empresa: str | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
) -> dict:
    """Retorna dados operacionais mensais consolidados da aviação doméstica: passageiros pagos, assentos, decolagens, RPK, ASK e load factor.

    Args:
        empresa: Sigla canônica da empresa (ex: 'LATAM', 'GOL', 'AZUL'). Se omitido, retorna todas.
        ano_inicio: Ano inicial (ex: 2022)
        ano_fim: Ano final (ex: 2026)
    """
    conds = ["1=1"]
    params = []
    if empresa:
        conds.append("sigla_atual = %s")
        params.append(empresa.strip().upper())
    if ano_inicio:
        conds.append("ano >= %s")
        params.append(ano_inicio)
    if ano_fim:
        conds.append("ano <= %s")
        params.append(ano_fim)

    sql = f"""
        SELECT
            sigla_atual,
            nome_comercial,
            periodo,
            ano,
            mes,
            pax_pagos,
            assentos_totais,
            decolagens,
            round(load_factor::numeric, 4) AS load_factor,
            rpk,
            ask
        FROM v_operacional_mensal
        WHERE {" AND ".join(conds)}
        ORDER BY ano DESC, mes DESC, sigla_atual;
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            colunas = [d[0] for d in cur.description]
            linhas = cur.fetchall()
            return _tabular(colunas, [list(r) for r in linhas])
    finally:
        conn.close()


@mcp.tool()
def check_data_integrity() -> dict:
    """Executa a bateria de auditoria de integridade da base ANAC: volumetria, chaves duplicadas, nulos e sanidade estatística."""
    # Importar run_checks de scripts/check_integrity.py
    sys.path.insert(0, str(ROOT_DIR / "scripts"))
    try:
        from check_integrity import run_checks
        return run_checks()
    except Exception as e:
        return {"erro": f"Falha ao executar verificação de integridade: {e}"}


# ---------- Execução ----------

def main():
    parser = argparse.ArgumentParser(description="ANAC Aviation Analytics MCP Server")
    parser.add_argument("--http", action="store_true", help="Rodar servidor HTTP em vez de stdio")
    parser.add_argument("--host", default="127.0.0.1", help="Host HTTP (padrão: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8766, help="Porta HTTP (padrão: 8766)")
    args = parser.parse_args()

    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(f"ANAC MCP Server rodando em http://{args.host}:{args.port}/mcp", file=sys.stderr)
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()

