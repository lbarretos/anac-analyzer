import sys
import io
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))
from transform_stats import transform, _clean_chunk

SAMPLE_HEADER = (
    "EMPRESA (SIGLA);EMPRESA (Nome);ANO;MÊS;NATUREZA;"
    "AEROPORTO DE ORIGEM;AEROPORTO DE DESTINO;"
    "PASSAGEIROS PAGOS;PASSAGEIROS GRÁTIS;ASSENTOS COMERCIALIZADOS;"
    "DECOLAGENS;CARGA PAGA (KG);CORREIO (KG);DISTÂNCIA VOADA (KM);COMBUSTÍVEL (LITROS)"
)

def make_csv(*rows: str) -> str:
    return SAMPLE_HEADER + "\n" + "\n".join(rows)


def test_column_rename():
    csv = make_csv("LATAM;LATAM;2022;3;DOMÉSTICA;SBSP;SBGL;1000;10;120;5;0;0;850;500000")
    path = "/tmp/test_stats.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert "empresa_sigla" in df.columns
    assert "passageiros_pagos" in df.columns
    assert "distancia_km" in df.columns


def test_empresa_normalization():
    csv = make_csv(
        "TAM;TAM;2015;1;DOMÉSTICA;SBSP;SBGL;500;5;60;2;0;0;500;200000",
        "WEBJET;WEBJET;2015;1;DOMÉSTICA;SBSP;SBCT;200;2;30;1;0;0;400;100000",
    )
    path = "/tmp/test_norm.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert set(df["empresa_sigla"]) == {"LATAM", "GOL"}


def test_year_filter():
    csv = make_csv(
        "GOL;GOL;2009;12;DOMÉSTICA;SBSP;SBGL;300;3;40;1;0;0;600;150000",
        "GOL;GOL;2010;1;DOMÉSTICA;SBSP;SBGL;300;3;40;1;0;0;600;150000",
    )
    path = "/tmp/test_year.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert (df["ano"] >= 2010).all()
    assert len(df) == 1


def test_null_dropping():
    csv = make_csv(
        ";empresa_sem_sigla;2022;3;DOMÉSTICA;SBSP;SBGL;100;1;12;1;0;0;500;100000",
        "AZUL;AZUL;;3;DOMÉSTICA;SBSP;SBGL;100;1;12;1;0;0;500;100000",
    )
    path = "/tmp/test_null.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert len(df) == 0


def test_sentinel_for_null_icao():
    csv = make_csv("AZUL;AZUL;2022;3;DOMÉSTICA;;;100;1;12;1;0;0;500;100000")
    path = "/tmp/test_icao.csv"
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv)
    df = transform(path)
    assert (df["origem_icao"] == "UNKNOWN").all()
    assert (df["destino_icao"] == "UNKNOWN").all()
