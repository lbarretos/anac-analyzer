import os
from datetime import date as _date
from calendar import monthrange as _mr


def _rab_url() -> str:
    today = _date.today()
    # Tenta mês atual; fallback para mês anterior (caso o arquivo ainda não exista no dia 1)
    for year, month in [(today.year, today.month), (today.year if today.month > 1 else today.year - 1, today.month - 1 if today.month > 1 else 12)]:
        url = f"https://sistemas.anac.gov.br/dadosabertos/Aeronaves/RAB/Historico_RAB/{year}-{month:02d}.csv"
        return url  # download.py já lida com 404
    return ""

ANAC_STATS_URL = (
    "https://sistemas.anac.gov.br/dadosabertos/"
    "Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/"
    "Dados%20Estat%C3%ADsticos%20do%20Transporte%20A%C3%A9reo/"
    "Dados_Estatisticos.csv"
)
ANAC_TARIFAS_URL = (
    "https://sistemas.anac.gov.br/dadosabertos/"
    "Voos%20e%20opera%C3%A7%C3%B5es%20a%C3%A9reas/"
    "Tarifas%20A%C3%A9reas%20Dom%C3%A9sticas/"
    "Tarifas_Aereas_Domesticas.csv"
)
ANAC_RAB_URL = _rab_url()

DATABASE_URL = os.environ["DATABASE_URL"]

# Dados históricos antes de 2010 descartados (mantido para consistência do dataset)
ANAC_MIN_YEAR = 2010

# Fonte única de verdade para normalização de siglas
# Chave: como aparece nos CSVs de Dados Estatísticos e Tarifas
# Valor: sigla canônica
EMPRESA_MAP: dict[str, str] = {
    # Códigos ANAC (siglas curtas usadas nos CSVs de Dados Estatísticos)
    "AZU":          "AZUL",
    "GLO":          "GOL",
    "TIB":          "AZUL",    # TRIP Serviços de Suporte Aéreo → Azul
    "ACN":          "AZUL",    # Azul Conecta
    "ONE":          "AVIANCA", # Oceanair → Avianca Brasil
    "PTB":          "VOEPASS", # Passaredo → VoePass
    "WEB":          "GOL",     # Webjet → GOL
    "PAM":          "MAP",
    # Nomes por extenso (formato antigo dos CSVs)
    "TAM":          "LATAM",
    "LAN BRASIL":   "LATAM",
    "LAN":          "LATAM",
    "WEBJET":       "GOL",
    "TRIP":         "AZUL",
    "OCEAN AIR":    "AZUL",
    "PANTANAL":     "AZUL",
    "NOAR":         "AZUL",
    "PASSAREDO":    "VOEPASS",
    "AVIANCA":      "AVIANCA",
    "VARIG":        "VARIG",
    "BRA":          "BRA",
    "MAP":          "MAP",
    "GOL TP":       "GOL",
}
