import os
import sys
from pathlib import Path
import pytest
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
load_dotenv(ROOT_DIR / ".env")

from check_integrity import run_checks


@pytest.fixture(scope="session")
def integrity_results():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL não configurada no ambiente")
    return run_checks()


def test_database_connected(integrity_results):
    assert integrity_results["database"] is not None
    assert integrity_results["status"] in ("PASS", "FAIL")


def test_table_row_counts_and_freshness(integrity_results):
    tables = integrity_results["tables"]
    assert tables["stg_stats"]["rows"] > 100_000, "stg_stats deve ter mais de 100.000 linhas"
    assert tables["stg_tarifas"]["rows"] > 30_000, "stg_tarifas deve ter mais de 30.000 linhas"
    assert tables["stg_rab"]["rows"] > 20_000, "stg_rab deve ter mais de 20.000 aeronaves"
    assert tables["dim_empresa"]["rows"] >= 20, "dim_empresa deve conter ao menos 20 mapeamentos"


def test_materialized_views_populated(integrity_results):
    mvs = integrity_results["matviews"]
    assert mvs["v_operacional_mensal"]["rows"] > 0
    assert mvs["v_yield_trimestral"]["rows"] > 0
    assert mvs["v_frota_ativa"]["rows"] >= 4, "Deve conter LATAM, GOL, AZUL e VOEPASS"
    assert mvs["v_utilizacao_frota"]["rows"] > 0


def test_no_duplicate_keys(integrity_results):
    dup_checks = [c for c in integrity_results["integrity_checks"] if "Duplicatas" in c["name"]]
    for check in dup_checks:
        assert check["passed"] is True, f"Falha de duplicatas em: {check['table']}"
        assert check["duplicates_found"] == 0


def test_dimension_and_fleet_coverage(integrity_results):
    dim_check = next(c for c in integrity_results["integrity_checks"] if "dim_empresa" in c["name"] and "Match" in c["name"])
    assert dim_check["passed"] is True
    assert dim_check["coverage_pct"] >= 90.0, f"Cobertura dimensional de {dim_check['coverage_pct']}% < 90%"

    fleet_check = next(c for c in integrity_results["integrity_checks"] if "Frota RAB" in c["name"])
    assert fleet_check["passed"] is True
    assert fleet_check["matched_aircraft"] > 500


def test_domain_aviation_sanity(integrity_results):
    sanity = {c["metric"]: c for c in integrity_results["domain_sanity"]}

    # Load factor
    lf = sanity["Load Factor Doméstico"]
    assert lf["passed"] is True
    assert 0.60 <= lf["avg"] <= 0.90
    assert lf["anomalies"] == 0

    # RPK <= ASK
    rpk_ask = sanity["Consistência RPK <= ASK"]
    assert rpk_ask["passed"] is True
    assert rpk_ask["violations"] == 0

    # Tarifa média
    fare = sanity["Tarifa Média Doméstica (R$)"]
    assert fare["passed"] is True
    assert 100.0 <= fare["avg"] <= 3000.0

    # Yield nominal
    yd = sanity["Yield Nominal (R$/RPK) e PRASK"]
    assert yd["passed"] is True
    assert 0.05 <= yd["avg_yield"] <= 0.80

    # Frota ativa
    fleets = {f["empresa"]: f for f in integrity_results["fleet_summary"]}
    for emp in ["LATAM", "AZUL", "GOL"]:
        assert emp in fleets, f"{emp} deve estar presente na frota ativa"
        assert fleets[emp]["aeronaves"] > 100
        assert 10.0 <= fleets[emp]["idade_media"] <= 30.0

