import os
import sys
from pathlib import Path
import pytest
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts" / "mcp"))
sys.path.insert(0, str(ROOT_DIR / "scripts" / "eval"))
load_dotenv(ROOT_DIR / ".env")

import anac_mcp
from eval_llm import run_evaluation, load_golden


@pytest.fixture(scope="session")
def check_db():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL não configurada no ambiente")


def test_mcp_list_tables(check_db):
    res = anac_mcp.list_tables()
    assert "tabelas" in res
    nomes = [t["nome"] for t in res["tabelas"]]
    assert "stg_stats" in nomes
    assert "stg_tarifas" in nomes
    assert "stg_rab" in nomes
    assert "dim_empresa" in nomes
    assert "v_operacional_mensal" in nomes
    assert "v_yield_trimestral" in nomes
    assert "v_frota_ativa" in nomes
    assert "v_utilizacao_frota" in nomes


def test_mcp_describe_table(check_db):
    res = anac_mcp.describe_table("v_yield_trimestral")
    assert res.get("tabela") == "v_yield_trimestral"
    colunas = [c["coluna"] for c in res["colunas"]]
    assert "sigla_atual" in colunas
    assert "yield_nominal" in colunas
    assert "prask" in colunas
    assert "trimestre" in colunas


def test_mcp_resolve_airline(check_db):
    # Resolução exata e histórica
    res_tam = anac_mcp.resolve_airline("TAM")
    empresas_tam = [e["sigla_atual"] for e in res_tam["empresas"]]
    assert "LATAM" in empresas_tam

    res_web = anac_mcp.resolve_airline("WEBJET")
    empresas_web = [e["sigla_atual"] for e in res_web["empresas"]]
    assert "GOL" in empresas_web

    res_azul = anac_mcp.resolve_airline("AZUL")
    empresas_azul = [e["sigla_atual"] for e in res_azul["empresas"]]
    assert "AZUL" in empresas_azul


def test_mcp_safe_query(check_db):
    # SELECT válido
    res = anac_mcp.query("SELECT count(*) as total FROM dim_empresa;")
    assert "colunas" in res
    assert res["linhas"][0][0] >= 20

    # Bloqueio de injeção destrutiva
    res_drop = anac_mcp.query("DROP TABLE stg_stats;")
    assert "erro" in res_drop
    assert "Apenas consultas SELECT" in res_drop["erro"]

    res_update = anac_mcp.query("UPDATE dim_empresa SET ativa = FALSE;")
    assert "erro" in res_update


def test_mcp_domain_metrics_tools(check_db):
    # Yield
    res_yd = anac_mcp.get_yield_metrics(empresa="LATAM", ano_inicio=2024, ano_fim=2024)
    assert len(res_yd["linhas"]) > 0
    assert "yield_nominal_reais_rpk" in res_yd["colunas"]

    # Frota
    res_fl = anac_mcp.get_fleet_metrics(empresa="GOL")
    assert len(res_fl["linhas"]) == 1
    assert res_fl["linhas"][0][0] == "GOL"
    assert res_fl["linhas"][0][2] > 200  # Aeronaves ativas

    # Tráfego
    res_tr = anac_mcp.get_traffic_volume(empresa="AZUL", ano_inicio=2026, ano_fim=2026)
    assert len(res_tr["linhas"]) > 0

    # Utilização
    res_ut = anac_mcp.get_fleet_utilization(empresa="LATAM", ano_inicio=2026, ano_fim=2026)
    assert len(res_ut["linhas"]) > 0


def test_golden_eval_suite_100_percent(check_db):
    summary = run_evaluation()
    assert summary["status"] == "PASS"
    assert summary["accuracy_pct"] == 100.0, f"Acurácia de {summary['accuracy_pct']}% esperada ser 100%"
    assert summary["passed"] == 10
    assert summary["failed"] == 0

