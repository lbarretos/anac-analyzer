-- Views analíticas — Análise A4 (Utilização de Frota)
-- Requer: v_operacional_mensal (views_yield.sql)

-- ────────────────────────────────────────────
-- Frota ativa por empresa (sem dimensão temporal)
-- Usa snapshot mais recente do RAB.
-- situacao = 'RBAC 121' (grandes companhias) ou 'RBAC 135' (regionais)
-- ────────────────────────────────────────────
DROP MATERIALIZED VIEW IF EXISTS v_utilizacao_frota;
DROP MATERIALIZED VIEW IF EXISTS v_frota_ativa;

CREATE MATERIALIZED VIEW v_frota_ativa AS
SELECT
    e.sigla_atual,
    e.nome_comercial,
    COUNT(DISTINCT r.matricula)                                                      AS aeronaves_ativas,
    ROUND(AVG(DATE_PART('year', r.snapshot_date) - r.ano_fabricacao)::NUMERIC, 1)   AS idade_media,
    ROUND(AVG(r.assentos)::NUMERIC, 0)                                               AS assentos_medios,
    STRING_AGG(DISTINCT r.modelo, ', ' ORDER BY r.modelo)                            AS modelos
FROM stg_rab r
JOIN dim_empresa e ON r.operador ILIKE '%' || e.razao_social || '%'
                   OR e.razao_social ILIKE '%' || r.operador || '%'
WHERE r.situacao IN ('RBAC 121', 'RBAC 135')
GROUP BY 1, 2;

CREATE UNIQUE INDEX idx_v_frota_ativa_pk ON v_frota_ativa (sigla_atual);

-- ────────────────────────────────────────────
-- Utilização de frota: ASK por aeronave por mês
-- Join apenas por sigla_atual (RAB tem somente um snapshot recente)
-- ────────────────────────────────────────────
CREATE MATERIALIZED VIEW v_utilizacao_frota AS
SELECT
    o.sigla_atual,
    o.nome_comercial,
    o.periodo,
    o.ano,
    o.mes,
    o.ask,
    o.rpk,
    o.load_factor,
    o.decolagens,
    f.aeronaves_ativas,
    f.idade_media,
    f.assentos_medios,
    CASE WHEN f.aeronaves_ativas > 0
        THEN ROUND(o.ask / f.aeronaves_ativas, 0)
        ELSE NULL
    END AS ask_por_aeronave,
    CASE WHEN f.aeronaves_ativas > 0
        THEN ROUND(o.decolagens::NUMERIC / f.aeronaves_ativas, 1)
        ELSE NULL
    END AS ciclos_por_aeronave,
    CASE WHEN o.decolagens > 0
        THEN ROUND(o.ask / o.decolagens, 0)
        ELSE NULL
    END AS ask_por_decolagem
FROM v_operacional_mensal o
LEFT JOIN v_frota_ativa f ON o.sigla_atual = f.sigla_atual;

CREATE UNIQUE INDEX idx_v_utilizacao_frota_pk
    ON v_utilizacao_frota (sigla_atual, ano, mes);

-- Refresh (chamar após refresh das views de yield):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY v_frota_ativa;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY v_utilizacao_frota;

-- Acesso via API routes (Next.js) — sem GRANTs para roles específicas.
