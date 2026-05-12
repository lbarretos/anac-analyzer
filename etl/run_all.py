"""
Orquestrador do pipeline ETL.

Uso:
  python etl/run_all.py           # carga incremental (padrão)
  python etl/run_all.py --full    # reprocessa desde ANAC_MIN_YEAR

Ordem: download → transform → load → refresh views
Falha em uma fonte não aborta as demais (continue-on-error por fonte).
"""
import sys
import argparse
from pathlib import Path
from datetime import date

# Adicionar diretório etl/ ao path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

from download import download_all
from transform_stats import transform as transform_stats
from transform_tarifas import transform as transform_tarifas
from transform_rab import transform as transform_rab
from load_supabase import upsert_table, get_max_periodo, get_client, refresh_materialized_views


def run(full: bool = False) -> None:
    errors: list[str] = []

    # ── 1. Download ──────────────────────────────────────
    print("\n[1/4] Download das fontes ANAC...")
    try:
        paths = download_all()
    except Exception as e:
        print(f"  ERRO no download: {e}")
        sys.exit(1)

    # ── 2. Transform + Load: Dados Estatísticos ──────────
    print("\n[2/4] Dados Estatísticos...")
    try:
        df_stats = transform_stats(str(paths["stats"]))

        if not full:
            max_periodo = get_max_periodo("stg_stats")
            if max_periodo:
                ano_max, mes_max = max_periodo
                df_stats = df_stats[
                    (df_stats["ano"] > ano_max) |
                    ((df_stats["ano"] == ano_max) & (df_stats["mes"] > mes_max))
                ]
                print(f"  Incremental: {len(df_stats)} novas linhas (após {ano_max}-{mes_max:02d})")

        upsert_table(df_stats, "stg_stats")
    except Exception as e:
        print(f"  ERRO em Dados Estatísticos: {e}")
        errors.append(f"stg_stats: {e}")

    # ── 3. Transform + Load: Tarifas ─────────────────────
    print("\n[3/4] Tarifas Domésticas...")
    if paths["tarifas"] is None:
        print("  AVISO: arquivo de tarifas não disponível, pulando.")
    else:
        try:
            df_tarifas = transform_tarifas(str(paths["tarifas"]))
            upsert_table(df_tarifas, "stg_tarifas")
        except Exception as e:
            print(f"  ERRO em Tarifas: {e}")
            errors.append(f"stg_tarifas: {e}")

    # ── 4. Transform + Load: RAB ─────────────────────────
    print("\n[4/4] RAB...")
    try:
        snapshot = date.today().replace(day=1)
        df_rab = transform_rab(str(paths["rab"]), snapshot_date=snapshot)
        upsert_table(df_rab, "stg_rab")
    except Exception as e:
        print(f"  ERRO em RAB: {e}")
        errors.append(f"stg_rab: {e}")

    # ── 5. Refresh views materializadas ──────────────────
    print("\nRefreshando views materializadas...")
    try:
        refresh_materialized_views(get_client())
    except Exception as e:
        print(f"  AVISO: falha no refresh das views: {e}")
        # Não fatal — dados foram carregados, views serão refreshadas na próxima run

    # ── Resultado ─────────────────────────────────────────
    if errors:
        print(f"\nETL concluído com {len(errors)} erro(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nETL concluído com sucesso.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Reprocessar tudo desde ANAC_MIN_YEAR")
    args = parser.parse_args()
    run(full=args.full)
