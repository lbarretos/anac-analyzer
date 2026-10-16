import argparse
import sys
from datetime import date
from transform_tarifas import process_year
from load_supabase import upsert_table, refresh_materialized_views, _query_neon_http

def main():
    parser = argparse.ArgumentParser(description="Ingest ANAC domestic airfares by year into Neon DB.")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025, 2026],
                        help="Years to fetch, aggregate, and upsert")
    parser.add_argument("--refresh", action="store_true", default=True,
                        help="Refresh materialized views after load")
    args = parser.parse_args()

    for y in args.years:
        print(f"\n==========================================")
        print(f"  Iniciando processamento Tarifas {y}...")
        print(f"==========================================")
        df_year = process_year(y, max_workers=6)
        if df_year.empty:
            print(f"  [Tarifas {y}] Nenhum dado retornado.")
            continue
        print(f"  [Tarifas {y}] {len(df_year)} registros agregados por rota/trimestre.")
        print(df_year.groupby("trimestre").agg(
            rotas=("origem_icao", "count"),
            pax=("passageiros", "sum"),
            tarifa_media=("tarifa_media", "mean")
        ))
        print(f"  [Tarifas {y}] Enviando para Neon DB (stg_tarifas)...")
        total = upsert_table(df_year, "stg_tarifas", chunk_size=1000)
        print(f"  [Tarifas {y}] Sucesso: {total} linhas upsertadas.")

    if args.refresh:
        print("\n==========================================")
        print("  Atualizando views materializadas...")
        print("==========================================")
        refresh_materialized_views()
        print("  Materialized views atualizadas com sucesso!")

    # Verificação rápida
    print("\n==========================================")
    print("  Conferência stg_tarifas na base:")
    print("==========================================")
    res = _query_neon_http("""
        SELECT ano, trimestre, count(*) as rotas, sum(passageiros) as pax, round(avg(tarifa_media), 2) as tarifa_media
        FROM stg_tarifas
        GROUP BY ano, trimestre
        ORDER BY ano, trimestre;
    """)
    for row in res.get("rows", []):
        print(f"  Ano {row[0]} T{row[1]}: {row[2]} rotas | {int(row[3]):,} pax | Tarifa Média: R$ {row[4]}".replace(",", "."))

if __name__ == "__main__":
    main()

