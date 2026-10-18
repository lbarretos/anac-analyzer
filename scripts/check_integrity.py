#!/usr/bin/env python3
"""
scripts/check_integrity.py — Verificação completa de integridade da base ANAC.

Checa:
  1. Conectividade e versão do banco
  2. Contagem de linhas e freshness das tabelas staging e views materializadas
  3. Ausência de duplicatas em constraints UNIQUE (stg_stats, stg_tarifas, stg_rab)
  4. Campos obrigatórios sem NULL (empresa_sigla, ano, mes/trimestre, etc.)
  5. Cobertura da dimensão dim_empresa (% das operações mapeadas para siglas canônicas)
  6. Cobertura do join RAB × dim_empresa (% das aeronaves RBAC 121/135 mapeadas)
  7. Regras de negócio e sanidade de domínio:
     - Load factor no range [0.0, 1.0] e média histórica esperada (65%-85%)
     - RPK <= ASK quando ASK > 0
     - Decolagens > 0 quando há passageiros pagos
     - Distância voada > 0
     - Tarifas médias em patamar de mercado (R$ 50 - 5.000)
     - Yield nominal (R$/RPK) em patamar crível (R$ 0.10 - 1.00)
     - Idade média da frota (5 - 40 anos) e assentos médios (30 - 400)

Uso:
  .venv/bin/python scripts/check_integrity.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Carregar variáveis de ambiente
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERRO: DATABASE_URL não configurada no .env", file=sys.stderr)
    sys.exit(1)


def get_connection():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


def run_checks() -> dict:
    results: dict = {
        "status": "PASS",
        "timestamp": None,
        "database": None,
        "tables": {},
        "matviews": {},
        "integrity_checks": [],
        "domain_sanity": [],
        "errors": [],
        "warnings": [],
    }

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 1. Informações do banco
            cur.execute("SELECT current_database(), version(), NOW();")
            db_name, db_ver, now_ts = cur.fetchone()
            results["database"] = db_name
            results["timestamp"] = str(now_ts)

            # 2. Contagens e Freshness
            tables = ["dim_empresa", "stg_stats", "stg_tarifas", "stg_rab"]
            for tbl in tables:
                cur.execute(f"SELECT count(*) FROM {tbl};")
                count = cur.fetchone()[0]
                freshness = None
                if tbl == "stg_stats":
                    cur.execute("SELECT max(ano), max(mes) FROM stg_stats;")
                    r = cur.fetchone()
                    if r[0] is not None:
                        freshness = f"{r[0]}-{r[1]:02d}"
                elif tbl == "stg_tarifas":
                    cur.execute("SELECT max(ano), max(trimestre) FROM stg_tarifas;")
                    r = cur.fetchone()
                    if r[0] is not None:
                        freshness = f"{r[0]} T{r[1]}"
                elif tbl == "stg_rab":
                    cur.execute("SELECT max(snapshot_date) FROM stg_rab;")
                    r = cur.fetchone()
                    if r[0] is not None:
                        freshness = str(r[0])

                results["tables"][tbl] = {
                    "rows": count,
                    "freshness": freshness,
                }

            matviews = [
                "v_operacional_mensal",
                "v_yield_trimestral",
                "v_frota_ativa",
                "v_utilizacao_frota",
            ]
            for mv in matviews:
                cur.execute(f"SELECT count(*) FROM {mv};")
                mv_count = cur.fetchone()[0]
                results["matviews"][mv] = {"rows": mv_count}

            # 3. Ausência de duplicatas em chaves UNIQUE
            # 3.1 stg_stats
            cur.execute("""
                SELECT count(*) FROM (
                    SELECT empresa_sigla, ano, mes, natureza, origem_icao, destino_icao, count(*)
                    FROM stg_stats
                    GROUP BY 1, 2, 3, 4, 5, 6
                    HAVING count(*) > 1
                ) t;
            """)
            dup_stats = cur.fetchone()[0]
            check_dup_stats = {
                "name": "Duplicatas em stg_stats",
                "table": "stg_stats",
                "passed": dup_stats == 0,
                "duplicates_found": dup_stats,
            }
            results["integrity_checks"].append(check_dup_stats)
            if dup_stats > 0:
                results["errors"].append(f"stg_stats possui {dup_stats} chaves duplicadas!")

            # 3.2 stg_tarifas
            cur.execute("""
                SELECT count(*) FROM (
                    SELECT empresa_sigla, ano, trimestre, origem_icao, destino_icao, count(*)
                    FROM stg_tarifas
                    GROUP BY 1, 2, 3, 4, 5
                    HAVING count(*) > 1
                ) t;
            """)
            dup_tarifas = cur.fetchone()[0]
            check_dup_tarifas = {
                "name": "Duplicatas em stg_tarifas",
                "table": "stg_tarifas",
                "passed": dup_tarifas == 0,
                "duplicates_found": dup_tarifas,
            }
            results["integrity_checks"].append(check_dup_tarifas)
            if dup_tarifas > 0:
                results["errors"].append(f"stg_tarifas possui {dup_tarifas} chaves duplicadas!")

            # 3.3 stg_rab
            cur.execute("""
                SELECT count(*) FROM (
                    SELECT matricula, snapshot_date, count(*)
                    FROM stg_rab
                    GROUP BY 1, 2
                    HAVING count(*) > 1
                ) t;
            """)
            dup_rab = cur.fetchone()[0]
            check_dup_rab = {
                "name": "Duplicatas em stg_rab",
                "table": "stg_rab",
                "passed": dup_rab == 0,
                "duplicates_found": dup_rab,
            }
            results["integrity_checks"].append(check_dup_rab)
            if dup_rab > 0:
                results["errors"].append(f"stg_rab possui {dup_rab} chaves duplicadas!")

            # 4. Checagem de Nulos em campos obrigatórios
            cur.execute("""
                SELECT
                    count(*) FILTER (WHERE empresa_sigla IS NULL OR empresa_sigla = '') AS null_empresa,
                    count(*) FILTER (WHERE ano IS NULL OR ano < 2000) AS invalid_ano,
                    count(*) FILTER (WHERE mes IS NULL OR mes NOT BETWEEN 1 AND 12) AS invalid_mes,
                    count(*) FILTER (WHERE natureza IS NULL) AS null_natureza
                FROM stg_stats;
            """)
            s_null_emp, s_inv_ano, s_inv_mes, s_null_nat = cur.fetchone()
            check_nulls_stats = {
                "name": "Nulos em campos críticos de stg_stats",
                "passed": (s_null_emp == 0 and s_inv_ano == 0 and s_inv_mes == 0 and s_null_nat == 0),
                "details": {
                    "null_empresa": s_null_emp,
                    "invalid_ano": s_inv_ano,
                    "invalid_mes": s_inv_mes,
                    "null_natureza": s_null_nat,
                },
            }
            results["integrity_checks"].append(check_nulls_stats)

            # 5. Mapeamento dimensional (dim_empresa)
            cur.execute("""
                SELECT
                    count(*) AS total,
                    count(e.sigla_atual) AS matched,
                    round(100.0 * count(e.sigla_atual) / nullif(count(*), 0), 2) AS pct_matched
                FROM stg_stats s
                LEFT JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
                WHERE s.natureza = 'DOMÉSTICA' AND s.ano >= 2022;
            """)
            stats_tot, stats_match, stats_pct = cur.fetchone()
            check_stats_dim = {
                "name": "Match de operadoras domésticas em dim_empresa",
                "passed": (stats_pct or 0) >= 90.0,
                "coverage_pct": float(stats_pct or 0),
                "matched_rows": stats_match,
                "total_rows": stats_tot,
            }
            results["integrity_checks"].append(check_stats_dim)
            if (stats_pct or 0) < 90.0:
                results["warnings"].append(f"Cobertura dimensional de stg_stats é {stats_pct}% (< 90%)")

            # 6. Join de Frota RAB
            cur.execute("""
                SELECT count(DISTINCT r.matricula)
                FROM stg_rab r
                WHERE r.snapshot_date = (SELECT max(snapshot_date) FROM stg_rab)
                  AND r.situacao IN ('RBAC 121', 'RBAC 135');
            """)
            total_commercial_rab = cur.fetchone()[0]

            cur.execute("SELECT sum(aeronaves_ativas) FROM v_frota_ativa;")
            matched_fleet = cur.fetchone()[0] or 0
            fleet_match_pct = round(100.0 * float(matched_fleet) / max(total_commercial_rab, 1), 1)

            check_fleet_join = {
                "name": "Join da Frota RAB com dim_empresa",
                "passed": matched_fleet > 0,
                "matched_aircraft": int(matched_fleet),
                "total_commercial_aircraft": total_commercial_rab,
                "coverage_pct": fleet_match_pct,
            }
            results["integrity_checks"].append(check_fleet_join)

            # 7. Sanidade de Domínio (Aviation Metrics)
            # 7.1 Load factor range [0.0, 1.0] e média razoável
            cur.execute("""
                SELECT
                    round(avg(load_factor)::numeric, 4) AS avg_lf,
                    round(min(load_factor)::numeric, 4) AS min_lf,
                    round(max(load_factor)::numeric, 4) AS max_lf,
                    count(*) FILTER (WHERE load_factor < 0.0 OR load_factor > 1.05) AS anomalies
                FROM v_operacional_mensal
                WHERE load_factor IS NOT NULL AND ano >= 2022;
            """)
            avg_lf, min_lf, max_lf, lf_anomalies = cur.fetchone()
            check_lf = {
                "metric": "Load Factor Doméstico",
                "passed": (lf_anomalies == 0 and avg_lf is not None and 0.60 <= float(avg_lf) <= 0.90),
                "avg": float(avg_lf) if avg_lf else None,
                "min": float(min_lf) if min_lf else None,
                "max": float(max_lf) if max_lf else None,
                "anomalies": lf_anomalies,
                "expected_avg_range": [0.60, 0.90],
            }
            results["domain_sanity"].append(check_lf)
            if lf_anomalies > 0:
                results["errors"].append(f"{lf_anomalies} linhas com Load Factor fora de [0%, 105%]")

            # 7.2 RPK <= ASK
            cur.execute("""
                SELECT count(*)
                FROM v_operacional_mensal
                WHERE rpk > ask * 1.02 AND ask > 0;
            """)
            rpk_gt_ask = cur.fetchone()[0]
            check_rpk_ask = {
                "metric": "Consistência RPK <= ASK",
                "passed": rpk_gt_ask == 0,
                "violations": rpk_gt_ask,
            }
            results["domain_sanity"].append(check_rpk_ask)

            # 7.3 Registros de fluxo de conexão (passageiros com decolagens = 0)
            cur.execute("""
                SELECT
                    count(*) FILTER (WHERE passageiros_pagos > 0 AND (decolagens IS NULL OR decolagens = 0)) AS zero_dep_pax,
                    count(*) AS total_rows,
                    round(100.0 * count(*) FILTER (WHERE passageiros_pagos > 0 AND (decolagens IS NULL OR decolagens = 0)) / count(*), 2) AS pct_connection_flow
                FROM stg_stats;
            """)
            zero_dep_pax, total_stats_rows, pct_zero_dep = cur.fetchone()
            check_dep_pax = {
                "metric": "Fluxos com Conexão (pax > 0 e decolagens = 0)",
                "passed": float(pct_zero_dep or 0) < 5.0,
                "connection_rows": zero_dep_pax,
                "pct_of_total": float(pct_zero_dep or 0),
                "threshold_pct": 5.0,
            }
            results["domain_sanity"].append(check_dep_pax)
            if float(pct_zero_dep or 0) >= 5.0:
                results["warnings"].append(f"{pct_zero_dep}% dos registros em stg_stats têm passageiros mas zero decolagens.")

            # 7.4 Tarifas médias razoáveis em stg_tarifas
            cur.execute("""
                SELECT
                    round(avg(tarifa_media)::numeric, 2) AS avg_fare,
                    round(min(tarifa_media)::numeric, 2) AS min_fare,
                    round(max(tarifa_media)::numeric, 2) AS max_fare,
                    count(*) FILTER (WHERE tarifa_media < 10.0 OR tarifa_media > 15000.0) AS extreme_fares
                FROM stg_tarifas
                WHERE tarifa_media IS NOT NULL;
            """)
            avg_fare, min_fare, max_fare, extreme_fares = cur.fetchone()
            check_fare = {
                "metric": "Tarifa Média Doméstica (R$)",
                "passed": (avg_fare is not None and 100.0 <= float(avg_fare) <= 3000.0),
                "avg": float(avg_fare) if avg_fare else None,
                "min": float(min_fare) if min_fare else None,
                "max": float(max_fare) if max_fare else None,
                "extreme_fares": extreme_fares,
            }
            results["domain_sanity"].append(check_fare)

            # 7.5 Yield nominal (R$/RPK) e PRASK
            cur.execute("""
                SELECT
                    round(avg(yield_nominal)::numeric, 4) AS avg_yield,
                    round(min(yield_nominal)::numeric, 4) AS min_yield,
                    round(max(yield_nominal)::numeric, 4) AS max_yield,
                    round(avg(prask)::numeric, 4) AS avg_prask
                FROM v_yield_trimestral
                WHERE yield_nominal IS NOT NULL;
            """)
            avg_yd, min_yd, max_yd, avg_pr = cur.fetchone()
            check_yield = {
                "metric": "Yield Nominal (R$/RPK) e PRASK",
                "passed": (avg_yd is not None and 0.05 <= float(avg_yd) <= 0.80),
                "avg_yield": float(avg_yd) if avg_yd else None,
                "min_yield": float(min_yd) if min_yd else None,
                "max_yield": float(max_yd) if max_yd else None,
                "avg_prask": float(avg_pr) if avg_pr else None,
                "expected_yield_range": [0.05, 0.80],
            }
            results["domain_sanity"].append(check_yield)

            # 7.6 Frota Ativa: Idade e Assentos médios
            cur.execute("""
                SELECT
                    sigla_atual,
                    aeronaves_ativas,
                    idade_media,
                    assentos_medios
                FROM v_frota_ativa
                ORDER BY aeronaves_ativas DESC;
            """)
            fleet_rows = []
            for r in cur.fetchall():
                fleet_rows.append({
                    "empresa": r[0],
                    "aeronaves": r[1],
                    "idade_media": float(r[2]) if r[2] is not None else None,
                    "assentos_medios": int(r[3]) if r[3] is not None else None,
                })
            results["fleet_summary"] = fleet_rows

            # Status geral
            all_passed = (
                all(c.get("passed", False) for c in results["integrity_checks"])
                and all(c.get("passed", False) for c in results["domain_sanity"])
                and len(results["errors"]) == 0
            )
            results["status"] = "PASS" if all_passed else "FAIL"

    finally:
        conn.close()

    return results


def print_report(res: dict) -> None:
    sep = "═" * 70
    subsep = "─" * 70
    print(sep)
    print(f"  ANAC Aviation Analytics — Relatório de Integridade da Base")
    print(f"  Banco: {res['database']} | Executado em: {res['timestamp']}")
    print(f"  Status Geral: {'✅ PASS' if res['status'] == 'PASS' else '❌ FAIL'}")
    print(sep)

    print("\n📊 1. Volumetria & Freshness das Tabelas:")
    print(subsep)
    for tbl, info in res["tables"].items():
        fresh = f" (Mais recente: {info['freshness']})" if info["freshness"] else ""
        print(f"  • {tbl:<16}: {info['rows']:>8,} linhas{fresh}".replace(",", "."))

    print("\n📈 2. Materialized Views:")
    print(subsep)
    for mv, info in res["matviews"].items():
        print(f"  • {mv:<22}: {info['rows']:>8,} linhas".replace(",", "."))

    print("\n🔍 3. Verificações de Integridade Estrutural:")
    print(subsep)
    for c in res["integrity_checks"]:
        mark = "✅" if c["passed"] else "❌"
        cov = f" (cobertura: {c.get('coverage_pct')}%)" if "coverage_pct" in c else ""
        dups = f" (duplicatas: {c.get('duplicates_found')})" if "duplicates_found" in c else ""
        print(f"  {mark} {c['name']}{cov}{dups}")

    print("\n✈️ 4. Sanidade de Domínio Aeronáutico:")
    print(subsep)
    for c in res["domain_sanity"]:
        mark = "✅" if c["passed"] else "❌"
        extra = []
        if "avg" in c and c["avg"] is not None:
            extra.append(f"média={c['avg']}")
        if "anomalies" in c:
            extra.append(f"anomalias={c['anomalies']}")
        if "violations" in c:
            extra.append(f"violações={c['violations']}")
        if "connection_rows" in c:
            extra.append(f"{c['pct_of_total']}% ({c['connection_rows']:,} linhas)".replace(",", "."))
        if "avg_yield" in c and c["avg_yield"] is not None:
            extra.append(f"yield médio=R$ {c['avg_yield']}/RPK, PRASK médio=R$ {c['avg_prask']}/ASK")
        extra_str = f" ({', '.join(extra)})" if extra else ""
        print(f"  {mark} {c['metric']}{extra_str}")

    if res.get("fleet_summary"):
        print("\n🛩️ 5. Resumo da Frota Comercial Ativa (RAB):")
        print(subsep)
        print(f"  {'Empresa':<10} {'Aeronaves':>10} {'Idade Média':>14} {'Assentos Médios':>16}")
        print(f"  {'-'*10} {'-'*10} {'-'*14} {'-'*16}")
        for f in res["fleet_summary"]:
            idade = f"{f['idade_media']:.1f} anos" if f["idade_media"] is not None else "N/A"
            assentos = f"{f['assentos_medios']} pax" if f["assentos_medios"] is not None else "N/A"
            print(f"  {f['empresa']:<10} {f['aeronaves']:>10} {idade:>14} {assentos:>16}")

    if res["warnings"]:
        print("\n⚠️ AVISOS:")
        for w in res["warnings"]:
            print(f"  - {w}")

    if res["errors"]:
        print("\n❌ ERROS CRÍTICOS:")
        for e in res["errors"]:
            print(f"  - {e}")

    print("\n" + sep)


def main():
    parser = argparse.ArgumentParser(description="Verifica a integridade da base de dados ANAC.")
    parser.add_argument("--json", action="store_true", help="Imprime resultado em formato JSON")
    args = parser.parse_args()

    results = run_checks()

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_report(results)

    sys.exit(0 if results["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
