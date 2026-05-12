-- ANAC Aviation Analytics — DDL
-- Filtro de dados: ano >= 2010

-- ────────────────────────────────────────────
-- Tabela de normalização de empresas
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_empresa (
    sigla_raw       TEXT PRIMARY KEY,   -- sigla como aparece no CSV de Dados Estatísticos
    sigla_atual     TEXT NOT NULL,      -- sigla canônica
    nome_comercial  TEXT,
    icao            TEXT,
    razao_social    TEXT,               -- razão social como aparece no RAB (OPERADOR)
    ativa           BOOLEAN DEFAULT TRUE
);

-- ────────────────────────────────────────────
-- Staging: Dados Estatísticos
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stg_stats (
    id                          BIGSERIAL PRIMARY KEY,
    empresa_sigla               TEXT NOT NULL,
    empresa_nome                TEXT,
    ano                         SMALLINT NOT NULL,
    mes                         SMALLINT NOT NULL,
    natureza                    TEXT,
    origem_icao                 TEXT NOT NULL DEFAULT 'UNKNOWN',
    destino_icao                TEXT NOT NULL DEFAULT 'UNKNOWN',
    passageiros_pagos           INTEGER,
    passageiros_gratis          INTEGER,
    assentos_disponibilizados   INTEGER,
    decolagens                  INTEGER,
    carga_kg                    NUMERIC,
    correio_kg                  NUMERIC,
    distancia_km                NUMERIC,
    combustivel_litros          NUMERIC,
    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_sigla, ano, mes, natureza, origem_icao, destino_icao)
);

CREATE INDEX IF NOT EXISTS idx_stg_stats_empresa_periodo
    ON stg_stats (empresa_sigla, ano, mes);

CREATE INDEX IF NOT EXISTS idx_stg_stats_natureza
    ON stg_stats (natureza);

-- ────────────────────────────────────────────
-- Staging: Tarifas Aéreas Domésticas (granularidade TRIMESTRAL)
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stg_tarifas (
    id              BIGSERIAL PRIMARY KEY,
    empresa_sigla   TEXT NOT NULL,
    ano             SMALLINT NOT NULL,
    trimestre       SMALLINT NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    origem_icao     TEXT NOT NULL DEFAULT 'UNKNOWN',
    destino_icao    TEXT NOT NULL DEFAULT 'UNKNOWN',
    tarifa_media    NUMERIC,
    passageiros     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_sigla, ano, trimestre, origem_icao, destino_icao)
);

CREATE INDEX IF NOT EXISTS idx_stg_tarifas_empresa_periodo
    ON stg_tarifas (empresa_sigla, ano, trimestre);

-- ────────────────────────────────────────────
-- Staging: RAB — Registro Aeronáutico Brasileiro
-- ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stg_rab (
    id              BIGSERIAL PRIMARY KEY,
    matricula       TEXT NOT NULL,
    operador        TEXT,               -- razão social completa ("TAM LINHAS AÉREAS S.A.")
    fabricante      TEXT,
    modelo          TEXT,
    ano_fabricacao  SMALLINT,
    assentos        SMALLINT,
    mtow_kg         INTEGER,
    categoria       TEXT,
    situacao        TEXT,
    snapshot_date   DATE NOT NULL,
    UNIQUE (matricula, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_stg_rab_operador
    ON stg_rab (operador);

-- Acesso controlado via API routes (Next.js) e connection string direta (ETL).
-- Sem RLS — dados públicos ANAC, nada sensível.
