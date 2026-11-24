"""
Orquestrador do pipeline ETL.

Uso:
  python etl/run_all.py           # carga incremental (padrão)
  python etl/run_all.py --full    # reprocessa desde ANAC_MIN_YEAR

Ordem: download → transform → load → refresh views
Falha em uma fonte não aborta as demais (continue-on-error por fonte).
"""
import sys
import time
import argparse
from pathlib import Path
from datetime import date

# Adicionar diretório etl/ ao path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

from download import download_all
from transform_stats import transform as transform_stats
from transform_tarifas import transform as transform_tarifas, process_year as process_year_tarifas
from transform_rab import transform as transform_rab
from load_supabase import upsert_table, get_max_periodo, get_client, refresh_materialized_views
from config import ANAC_MIN_YEAR


def _send_telegram(status: str, duracao: str, erros: str = "", detalhes: str = "") -> None:
    try:
        from notify_telegram import notify_telegram
        notify_telegram(
            projeto="ANAC",
            status=status,
            duracao=duracao,
            erros=erros,
            detalhes=detalhes,
        )
    except Exception as e:
        print(f"  AVISO: falha ao enviar notificação Telegram: {e}")


def run(full: bool = False) -> None:
    start_time = time.time()
    errors: list[str] = []

    # ── 1. Download ──────────────────────────────────────
    print("\n[1/4] Download das fontes ANAC...")
    try:
        paths = download_all()
    except Exception as e:
        print(f"  ERRO no download: {e}")
        duracao_str = f"{round((time.time() - start_time) / 60, 1)} min"
        _send_telegram("falha", duracao_str, erros=f"download: {e}", detalhes="Falha no download das fontes ANAC")
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
    try:
        current_year = date.today().year
        if full:
            start_year = ANAC_MIN_YEAR
        else:
            max_periodo = get_max_periodo("stg_tarifas")
            start_year = max_periodo[0] if max_periodo else ANAC_MIN_YEAR

        for y in range(start_year, current_year + 1):
            print(f"  [Tarifas] Processando ano {y}...")
            df_year = process_year_tarifas(y)
            if not df_year.empty:
                upsert_table(df_year, "stg_tarifas")
            else:
                print(f"  [Tarifas] Sem dados para {y}")
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
    duracao_str = f"{round((time.time() - start_time) / 60, 1)} min"
    if errors:
        print(f"\nETL concluído com {len(errors)} erro(s):")
        for err in errors:
            print(f"  - {err}")
        _send_telegram(
            status="falha",
            duracao=duracao_str,
            erros="; ".join(errors),
            detalhes=f"{len(errors)} erro(s) durante o ETL",
        )
        sys.exit(1)
    else:
        print("\nETL concluído com sucesso.")
        _send_telegram(
            status="sucesso",
            duracao=duracao_str,
            detalhes="ETL completo executado com sucesso (stats, tarifas, rab, views)",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Reprocessar tudo desde ANAC_MIN_YEAR")
    args = parser.parse_args()
    run(full=args.full)
