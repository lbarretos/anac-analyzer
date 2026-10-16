import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))
from transform_tarifas import transform

HEADER = "EMPRESA (SIGLA);ANO;TRIMESTRE;ORIGEM;DESTINO;TARIFA;PASSAGEIROS"

def make_csv(*rows: str) -> str:
    return HEADER + "\n" + "\n".join(rows)


def test_trimestre_populated():
    csv = make_csv(
        "LATAM;2022;1;SBSP;SBGL;350,00;1000",
        "LATAM;2022;2;SBSP;SBGL;380,00;1100",
    )
    path = "/tmp/test_tarifas.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert "trimestre" in df.columns
    assert set(df["trimestre"]) == {1, 2}


def test_trimestre_range():
    csv = make_csv(
        "GOL;2023;1;SBSP;SBBR;300,00;500",
        "GOL;2023;4;SBSP;SBBR;320,00;550",
        "GOL;2023;5;SBSP;SBBR;999,00;1",  # inválido
    )
    path = "/tmp/test_tarifas_range.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert df["trimestre"].between(1, 4).all()
    assert len(df) == 2


def test_year_filter():
    csv = make_csv(
        "AZUL;2009;4;SBSP;SBGL;250,00;400",  # filtrado
        "AZUL;2010;1;SBSP;SBGL;260,00;420",  # mantido
    )
    path = "/tmp/test_tarifas_year.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert (df["ano"] >= 2010).all()
    assert len(df) == 1


def test_dedup():
    csv = make_csv(
        "LATAM;2022;1;SBSP;SBGL;350,00;1000",
        "LATAM;2022;1;SBSP;SBGL;350,00;1000",  # duplicata
    )
    path = "/tmp/test_tarifas_dedup.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert len(df) == 1


def test_decimal_formats():
    # Testa formato antigo com vírgula e formato novo (pós-out/2024) com ponto
    csv = make_csv(
        "LATAM;2024;3;SBSP;SBGL;350,50;100",
        "LATAM;2024;4;SBSP;SBGL;420.75;100",
    )
    path = "/tmp/test_tarifas_decimals.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert len(df) == 2
    row_comma = df[df["trimestre"] == 3].iloc[0]
    row_dot = df[df["trimestre"] == 4].iloc[0]
    assert row_comma["tarifa_media"] == 350.50
    assert row_dot["tarifa_media"] == 420.75


def test_canonical_column_variations():
    # Testa cabeçalho alternativo com prefixos nr_/sg_
    csv = (
        "SG_EMPRESA_ICAO;NR_ANO_REFERENCIA;NR_MES_REFERENCIA;SG_ICAO_ORIGEM;SG_ICAO_DESTINO;NR_TARIFA;NR_ASSENTOS\n"
        "GLO;2024;10;SBBR;SBCF;299.90;50\n"
    )
    path = "/tmp/test_tarifas_canonical.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert len(df) == 1
    assert df.iloc[0]["empresa_sigla"] == "GOL"
    assert df.iloc[0]["ano"] == 2024
    assert df.iloc[0]["trimestre"] == 4
    assert df.iloc[0]["tarifa_media"] == 299.90
    assert df.iloc[0]["passageiros"] == 50

