-- Seed: dim_empresa
-- sigla_raw: como aparece nos CSVs de Dados Estatísticos e Tarifas
-- razao_social: padrão normalizado para correspondência com OPERADOR do RAB
-- Expandir conforme novos operadores aparecerem nos dados

INSERT INTO dim_empresa (sigla_raw, sigla_atual, nome_comercial, icao, razao_social, ativa) VALUES
-- LATAM (absorveu TAM, LAN Brasil)
('LATAM',       'LATAM', 'LATAM Airlines Brasil', 'TAM', 'TAM LINHAS AEREAS',              TRUE),
('TAM',         'LATAM', 'LATAM Airlines Brasil', 'TAM', 'TAM LINHAS AEREAS',              TRUE),
('LAN',         'LATAM', 'LATAM Airlines Brasil', 'TAM', 'LAN AIRLINES',                   TRUE),
('LAN BRASIL',  'LATAM', 'LATAM Airlines Brasil', 'TAM', 'LAN BRASIL',                     TRUE),

-- GOL (absorveu Webjet)
('GOL',         'GOL',   'GOL Linhas Aéreas',     'GLO', 'GOL LINHAS AEREAS',              TRUE),
('GLO',         'GOL',   'GOL Linhas Aéreas',     'GLO', 'GOL LINHAS AEREAS',              TRUE),
('GOL TP',      'GOL',   'GOL Linhas Aéreas',     'GLO', 'GOL TRANSPORTES AEREOS',         TRUE),
('WEBJET',      'GOL',   'GOL Linhas Aéreas',     'GLO', 'WEBJET LINHAS AEREAS',           FALSE),
('WEB',         'GOL',   'GOL Linhas Aéreas',     'GLO', 'WEBJET LINHAS AEREAS',           FALSE),

-- AZUL (absorveu TRIP, Azul Conecta)
('AZUL',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'AZUL LINHAS AEREAS',             TRUE),
('AZU',         'AZUL',  'Azul Linhas Aéreas',    'AZU', 'AZUL LINHAS AEREAS',             TRUE),
('ACN',         'AZUL',  'Azul Linhas Aéreas',    'AZU', 'AZUL CONECTA',                   TRUE),
('TRIP',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'TRIP LINHAS AEREAS',             FALSE),
('TIB',         'AZUL',  'Azul Linhas Aéreas',    'AZU', 'TRIP LINHAS AEREAS',             FALSE),
('PANTANAL',    'LATAM', 'LATAM Airlines Brasil', 'TAM', 'PANTANAL LINHAS AEREAS',         FALSE),
('NOAR',        'AZUL',  'Azul Linhas Aéreas',    'AZU', 'NOAR LINHAS AEREAS',             FALSE),

-- VOEPASS (ex-Passaredo)
('VOEPASS',     'VOEPASS','VoePass Linhas Aéreas', 'PTB', 'VOEPASS LINHAS AEREAS',         TRUE),
('PTB',         'VOEPASS','VoePass Linhas Aéreas', 'PTB', 'PASSAREDO TRANSPORTES AEREOS',  TRUE),
('PASSAREDO',   'VOEPASS','VoePass Linhas Aéreas', 'PTB', 'PASSAREDO TRANSPORTES AEREOS',  FALSE),

-- Outras
('MAP',         'MAP',   'MAP Linhas Aéreas',     'MAP', 'MAP TRANSPORTES AEREOS',          TRUE),
('PAM',         'MAP',   'MAP Linhas Aéreas',     'MAP', 'MAP TRANSPORTES AEREOS',          TRUE),
('AVIANCA',     'AVIANCA','Avianca Brasil',        'ONE', 'OCEANAIR LINHAS AEREAS',         FALSE),
('ONE',         'AVIANCA','Avianca Brasil',        'ONE', 'OCEANAIR LINHAS AEREAS',         FALSE),
('OCEAN AIR',   'AVIANCA','Avianca Brasil',        'ONE', 'OCEANAIR LINHAS AEREAS',         FALSE),
('BRA',         'BRA',   'BRA Transportes Aéreos','BRA', 'BRA - TRANSPORTES AEREOS',       FALSE),
('VARIG',       'VARIG', 'Varig',                 'VRG', 'VARIG',                           FALSE)

ON CONFLICT (sigla_raw) DO UPDATE
    SET sigla_atual    = EXCLUDED.sigla_atual,
        nome_comercial = EXCLUDED.nome_comercial,
        icao           = EXCLUDED.icao,
        razao_social   = EXCLUDED.razao_social,
        ativa          = EXCLUDED.ativa;
