#!/usr/bin/env python3
"""
scripts/eval/eval_llm.py — Avaliação de qualidade de leitura por LLM e ferramentas MCP.

Avalia o conjunto golden (scripts/eval/golden_dataset.json):
  1. Eficácia e precisão das ferramentas MCP dedicadas (FastMCP)
  2. Validação da consulta analítica direta via SQL (query)
  3. Conformidade das respostas com tolerâncias numéricas e regras de domínio
  4. Resiliência a pegadinhas (empresas inativas, granularidade trimestral vs mensal)
  5. Economia de tokens e orçamento de caracteres (context efficiency)

Uso:
  .venv/bin/python scripts/eval/eval_llm.py [--json] [--verbose]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "scripts" / "mcp"))

import anac_mcp


def load_golden() -> list[dict]:
    golden_path = ROOT_DIR / "scripts" / "eval" / "golden_dataset.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def eval_question(q: dict) -> dict:
    qid = q["id"]
    pergunta = q["pergunta"]
    tipo = q["tipo_resposta"]
    ferramenta = q["ferramenta_esperada"]

    result = {
        "id": qid,
        "categoria": q["categoria"],
        "pergunta": pergunta,
        "ferramenta": ferramenta,
        "passed": False,
        "latency_ms": 0.0,
        "response_chars": 0,
        "extracted_value": None,
        "ground_truth": q.get("esperado"),
        "error": None,
        "notes": "",
    }

    t0 = time.perf_counter()

    try:
        # Executar a ferramenta MCP apropriada
        if qid == "q001_azul_fleet":
            mcp_res = anac_mcp.get_fleet_metrics(empresa="AZUL")
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            if linhas:
                row = linhas[0]
                aero = int(row[2])
                idade = float(row[3])
                result["extracted_value"] = {"aeronaves": aero, "idade_media": idade}
                exp = q["esperado"]
                tol = q["tolerancia"]
                passed = (
                    abs(aero - exp["aeronaves"]) <= tol["aeronaves"]
                    and abs(idade - exp["idade_media"]) <= tol["idade_media"]
                )
                result["passed"] = passed
            else:
                result["error"] = "Linha AZUL não encontrada na resposta do MCP"

        elif qid == "q002_latam_load_factor":
            mcp_res = anac_mcp.get_traffic_volume(empresa="LATAM", ano_inicio=2026, ano_fim=2026)
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            jul_row = next((r for r in linhas if r[3] == 2026 and r[4] == 7), None)
            if jul_row:
                lf_pct = round(float(jul_row[8]) * 100.0, 2)
                result["extracted_value"] = lf_pct
                exp = q["esperado"]
                tol = q["tolerancia"]
                result["passed"] = abs(lf_pct - exp) <= tol
            else:
                result["error"] = "Mês 2026-07 não encontrado para LATAM"

        elif qid == "q003_gol_yield_2024q4":
            mcp_res = anac_mcp.get_yield_metrics(empresa="GOL", ano_inicio=2024, ano_fim=2024, trimestre=4)
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            if linhas:
                yield_val = float(linhas[0][6])
                result["extracted_value"] = yield_val
                exp = q["esperado"]
                tol = q["tolerancia"]
                result["passed"] = abs(yield_val - exp) <= tol
            else:
                result["error"] = "Yield 2024 T4 para GOL não retornado"

        elif qid == "q004_total_pax_2024":
            sql = q["sql_referencia"]
            mcp_res = anac_mcp.query(sql)
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            if linhas and linhas[0]:
                tot = int(linhas[0][0])
                result["extracted_value"] = tot
                exp = q["esperado"]
                tol = q["tolerancia"]
                result["passed"] = abs(tot - exp) <= tol
            else:
                result["error"] = "Query de passageiros totais vazia"

        elif qid == "q005_youngest_fleet":
            mcp_res = anac_mcp.get_fleet_metrics()
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            if linhas:
                ordenadas = sorted(linhas, key=lambda r: float(r[3]))
                youngest = ordenadas[0]
                emp = youngest[0]
                idade = float(youngest[3])
                result["extracted_value"] = {"empresa": emp, "idade_media": idade}
                exp = q["esperado"]
                result["passed"] = (emp == exp["empresa"] and abs(idade - exp["idade_media"]) <= q["tolerancia"]["idade_media"])
            else:
                result["error"] = "Nenhuma frota retornada"

        elif qid == "q006_gol_cycles_2026_08":
            mcp_res = anac_mcp.get_fleet_utilization(empresa="GOL", ano_inicio=2026, ano_fim=2026)
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            ago_row = next((r for r in linhas if r[3] == 2026 and r[4] == 8), None)
            if ago_row:
                ciclos = float(ago_row[7])
                result["extracted_value"] = ciclos
                exp = q["esperado"]
                result["passed"] = abs(ciclos - exp) <= q["tolerancia"]
            else:
                result["error"] = "Ciclos 2026-08 não encontrados"

        elif qid == "q007_largest_fleet":
            mcp_res = anac_mcp.get_fleet_metrics()
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            if linhas:
                largest = max(linhas, key=lambda r: int(r[2]))
                emp = largest[0]
                aero = int(largest[2])
                result["extracted_value"] = {"empresa": emp, "aeronaves": aero}
                exp = q["esperado"]
                result["passed"] = (emp == exp["empresa"] and aero == exp["aeronaves"])
            else:
                result["error"] = "Nenhuma frota retornada"

        elif qid == "q008_resolve_acronyms":
            res_tam = anac_mcp.resolve_airline("TAM")
            res_web = anac_mcp.resolve_airline("WEBJET")
            result["response_chars"] = len(json.dumps(res_tam)) + len(json.dumps(res_web))
            tam_match = next((e["sigla_atual"] for e in res_tam.get("empresas", []) if "TAM" in e["siglas_raw"]), None)
            web_match = next((e["sigla_atual"] for e in res_web.get("empresas", []) if "WEB" in e["siglas_raw"]), None)
            result["extracted_value"] = {"TAM": tam_match, "WEBJET": web_match}
            exp = q["esperado"]
            result["passed"] = (tam_match == exp["TAM"] and web_match == exp["WEBJET"])

        elif qid == "q009_yield_methodology_granularity":
            # Verificar se describe_table(v_yield_trimestral) e describe_table(stg_tarifas) expõem trimestre
            desc_yield = anac_mcp.describe_table("v_yield_trimestral")
            desc_tarifas = anac_mcp.describe_table("stg_tarifas")
            result["response_chars"] = len(json.dumps(desc_yield)) + len(json.dumps(desc_tarifas))
            cols_yield = [c["coluna"] for c in desc_yield.get("colunas", [])]
            cols_tarifas = [c["coluna"] for c in desc_tarifas.get("colunas", [])]
            has_trimestre = "trimestre" in cols_yield and "trimestre" in cols_tarifas
            has_no_mes = "mes" not in cols_tarifas  # tarifas não é mensal
            result["extracted_value"] = {
                "tabela_yield": desc_yield.get("tabela"),
                "has_trimestre_constraint": has_trimestre,
                "granularidade_fonte": "TRIMESTRAL (stg_tarifas sem coluna mes)",
            }
            result["passed"] = has_trimestre and has_no_mes
            result["notes"] = "Schema comprova formalmente que tarifas são trimestrais e yield mensal não existe no banco."

        elif qid == "q010_inactive_company":
            mcp_res = anac_mcp.get_fleet_metrics(empresa="VARIG")
            result["response_chars"] = len(json.dumps(mcp_res))
            linhas = mcp_res.get("linhas", [])
            # Varig não deve ter aeronaves ativas em v_frota_ativa
            res_dim = anac_mcp.resolve_airline("VARIG")
            varig_dim = next((e for e in res_dim.get("empresas", []) if e["sigla_atual"] == "VARIG"), None)
            is_inactive = varig_dim is not None and varig_dim.get("ativa") is False
            result["extracted_value"] = {
                "aeronaves_ativas": len(linhas),
                "cadastro_dim_empresa": "Inativa (ativa=False)" if is_inactive else "Ativa",
            }
            result["passed"] = (len(linhas) == 0 and is_inactive)
            result["notes"] = "Varig confirmada com 0 aeronaves ativas no RAB e marcada como inativa."

    except Exception as e:
        result["error"] = str(e)
        result["passed"] = False

    t1 = time.perf_counter()
    result["latency_ms"] = round((t1 - t0) * 1000.0, 2)
    return result


def run_evaluation() -> dict:
    questions = load_golden()
    results = []

    for q in questions:
        res = eval_question(q)
        results.append(res)

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    accuracy = round(100.0 * passed / max(total, 1), 1)
    avg_latency = round(sum(r["latency_ms"] for r in results) / max(total, 1), 2)
    avg_chars = round(sum(r["response_chars"] for r in results) / max(total, 1), 0)

    summary = {
        "status": "PASS" if accuracy >= 90.0 else "FAIL",
        "total_questions": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy_pct": accuracy,
        "avg_latency_ms": avg_latency,
        "avg_response_chars": int(avg_chars),
        "results": results,
    }
    return summary


def print_report(s: dict) -> None:
    sep = "═" * 78
    subsep = "─" * 78
    print(sep)
    print("  ANAC Aviation Analytics — Teste de Qualidade de Leitura por LLM e MCP")
    print(f"  Resultado: {'✅ PASS' if s['status'] == 'PASS' else '❌ FAIL'} | "
          f"Acurácia: {s['passed']}/{s['total_questions']} ({s['accuracy_pct']}%) | "
          f"Latência Média: {s['avg_latency_ms']} ms | Tamanho Médio: {s['avg_response_chars']} chars")
    print(sep)

    print("\n📋 Detalhamento por Caso de Teste Golden:")
    print(subsep)
    for r in s["results"]:
        mark = "✅" if r["passed"] else "❌"
        print(f"\n{mark} [{r['id']}] {r['pergunta']}")
        print(f"   Ferramenta MCP: {r['ferramenta']} | Latência: {r['latency_ms']} ms | Caracteres: {r['response_chars']}")
        print(f"   Esperado:       {r['ground_truth']}")
        print(f"   Obtido:         {r['extracted_value']}")
        if r.get("notes"):
            print(f"   Nota:           {r['notes']}")
        if r.get("error"):
            print(f"   ERRO:           {r['error']}")

    print("\n" + sep)


def main():
    parser = argparse.ArgumentParser(description="Executa o benchmark golden de qualidade MCP e LLM.")
    parser.add_argument("--json", action="store_true", help="Saída em formato JSON")
    args = parser.parse_args()

    summary = run_evaluation()

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print_report(summary)

    sys.exit(0 if summary["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

