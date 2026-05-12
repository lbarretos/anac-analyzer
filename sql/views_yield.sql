-- Views analíticas — Análise A1 (Yield / PRASK)
-- Nota metodológica: tarifa_media é tarifa amostrada de mercado (ANAC),
-- não receita contábil auditada. Yield/PRASK são proxies baseados em
-- dados públicos disponíveis.

-- ────────────────────────────────────────────
-- Operacional mensal por empresa (doméstico)
-- ────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS v_operacional_mensal AS
SELECT
    e.sigla_atual,
    e.nome_comercial,
    s.ano,
    s.mes,
    DATE_TRUNC('month', MAKE_DATE(s.ano, s.mes, 1))::DATE AS periodo,
    SUM(s.passageiros_pagos)                              AS pax_pagos,
    SUM(s.assentos_disponibilizados)                      AS assentos_totais,
    SUM(s.decolagens)                                     AS decolagens,
    SUM(s.passageiros_pagos * s.distancia_km)             AS rpk,
    SUM(s.assentos_disponibilizados * s.distancia_km)     AS ask,
    CASE WHEN SUM(s.assentos_disponibilizados * s.distancia_km) > 0
        THEN SUM(s.passageiros_pagos * s.distancia_km)::NUMERIC
           / SUM(s.assentos_disponibilizados * s.distancia_km)
        ELSE NULL
    END AS load_factor
FROM stg_stats s
JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
WHERE s.natureza = 'DOMÉSTICA'
  AND s.ano >= 2010
GROUP BY 1, 2, 3, 4, 5;

CREATE UNIQUE INDEX IF NOT EXISTS idx_v_operacional_mensal_pk
    ON v_operacional_mensal (sigla_atual, ano, mes);

-- ────────────────────────────────────────────
-- Yield e PRASK por empresa — granularidade TRIMESTRAL
-- (tarifas ANAC são trimestrais; yield mensal seria metodologicamente incorreto)
-- ────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS v_yield_trimestral AS
SELECT
    o.sigla_atual,
    o.nome_comercial,
    o.ano,
    CEIL(o.mes::NUMERIC / 3)::SMALLINT          AS trimestre,
    SUM(o.pax_pagos)                            AS pax_pagos,
    SUM(o.rpk)                                  AS rpk,
    SUM(o.ask)                                  AS ask,
    AVG(o.load_factor)                          AS load_factor,
    SUM(o.decolagens)                           AS decolagens,
    t.receita_proxy,
    t.pax_tarifas,
    CASE WHEN SUM(o.rpk) > 0
        THEN t.receita_proxy / SUM(o.rpk)
        ELSE NULL
    END AS yield_nominal,                        -- R$/RPK (proxy)
    CASE WHEN SUM(o.ask) > 0
        THEN t.receita_proxy / SUM(o.ask)
        ELSE NULL
    END AS prask                                 -- R$/ASK (proxy)
FROM v_operacional_mensal o
LEFT JOIN (
    SELECT
        e.sigla_atual,
        t.ano,
        t.trimestre,
        SUM(t.tarifa_media * t.passageiros) AS receita_proxy,
        SUM(t.passageiros)                  AS pax_tarifas
    FROM stg_tarifas t
    JOIN dim_empresa e ON t.empresa_sigla = e.sigla_raw
    GROUP BY 1, 2, 3
) t ON o.sigla_atual = t.sigla_atual
   AND o.ano         = t.ano
   AND CEIL(o.mes::NUMERIC / 3) = t.trimestre
GROUP BY 1, 2, 3, 4, t.receita_proxy, t.pax_tarifas;

CREATE UNIQUE INDEX IF NOT EXISTS idx_v_yield_trimestral_pk
    ON v_yield_trimestral (sigla_atual, ano, trimestre);

-- ────────────────────────────────────────────
-- Refresh (chamar após cada carga ETL)
-- ────────────────────────────────────────────
-- REFRESH MATERIALIZED VIEW CONCURRENTLY v_operacional_mensal;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY v_yield_trimestral;

-- Acesso via API routes (Next.js) — sem GRANTs para roles específicas.
