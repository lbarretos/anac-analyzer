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
