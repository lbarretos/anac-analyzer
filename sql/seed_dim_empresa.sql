-- Seed: dim_empresa
-- sigla_raw: como aparece nos CSVs de Dados Estatísticos e Tarifas
-- razao_social: como aparece no campo OPERADOR do RAB
-- Expandir conforme novos operadores aparecerem nos dados

INSERT INTO dim_empresa (sigla_raw, sigla_atual, nome_comercial, icao, razao_social, ativa) VALUES
-- LATAM (absorveu TAM, LAN Brasil)
('LATAM',       'LATAM', 'LATAM Airlines Brasil', 'TAM', 'LATAM AIRLINES GROUP S.A.',          TRUE),
('TAM',         'LATAM', 'LATAM Airlines Brasil', 'TAM', 'TAM LINHAS AEREAS S.A.',              TRUE),
('LAN',         'LATAM', 'LATAM Airlines Brasil', 'TAM', 'LAN AIRLINES S.A.',                   TRUE),
('LAN BRASIL',  'LATAM', 'LATAM Airlines Brasil', 'TAM', 'LAN BRASIL S.A.',                     TRUE),

-- GOL (absorveu Webjet)
('GOL',         'GOL',   'GOL Linhas Aéreas',     'GLO', 'GOL LINHAS AEREAS S.A.',              TRUE),
('WEBJET',      'GOL',   'GOL Linhas Aéreas',     'GLO', 'WEBJET LINHAS AEREAS S.A.',           FALSE),

-- AZUL (absorveu TRIP, Ocean Air, Pantanal, NOAR)
('AZUL',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'AZUL LINHAS AEREAS BRASILEIRAS S.A.', TRUE),
('TRIP',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'TRIP LINHAS AEREAS S.A.',             FALSE),
('OCEAN AIR',   'AZUL',  'Azul Linhas Aéreas',    'AZU', 'OCEAN AIR LINHAS AEREAS S.A.',        FALSE),
('PANTANAL',    'AZUL',  'Azul Linhas Aéreas',    'AZU', 'PANTANAL LINHAS AEREAS SUL MATO GROSSENSES S.A.', FALSE),
('NOAR',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'NOAR LINHAS AEREAS S.A.',             FALSE),

-- VOEPASS (ex-Passaredo)
('VOEPASS',     'VOEPASS','VoePass Linhas Aéreas', 'PTB', 'VOEPASS LINHAS AEREAS S.A.',         TRUE),
('PASSAREDO',   'VOEPASS','VoePass Linhas Aéreas', 'PTB', 'PASSAREDO TRANSPORTES AEREOS S.A.',  FALSE),

-- Outras ativas
('AVIANCA',     'AVIANCA','Avianca Brasil',        'ONE', 'OCEANAIR LINHAS AEREAS S.A.',         FALSE),
('BRA',         'BRA',   'BRA Transportes Aéreos','BRA', 'BRA - TRANSPORTES AEREOS S.A.',       FALSE),
('VARIG',       'VARIG', 'Varig',                 'VRG', 'VARIG S.A.',                           FALSE),
('MAP',         'MAP',   'MAP Linhas Aéreas',     'MAP', 'MAP TRANSPORTES AEREOS LTDA',          TRUE),
('GOL TP',      'GOL',   'GOL Linhas Aéreas',     'GLO', 'GOL TRANSPORTES AEREOS S.A.',          TRUE)

ON CONFLICT (sigla_raw) DO UPDATE
    SET sigla_atual    = EXCLUDED.sigla_atual,
        nome_comercial = EXCLUDED.nome_comercial,
        icao           = EXCLUDED.icao,
        razao_social   = EXCLUDED.razao_social,
        ativa          = EXCLUDED.ativa;
