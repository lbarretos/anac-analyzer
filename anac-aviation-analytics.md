# ANAC Aviation Analytics — Project Spec

Repositório público no GitHub com pipeline de dados da ANAC, armazenamento no Supabase e dashboard online via Vercel.

**Análises no escopo:**
- **A1 — Yield Real e PRASK implícito** (Dados Estatísticos × Tarifas Domésticas)
- **A4 — Utilização de frota e ASK/aeronave** (Dados Estatísticos × RAB)

---

## I. Estrutura do Repositório

```
anac-aviation-analytics/
├── .github/
│   └── workflows/
│       ├── ingest.yml          # ETL agendado (mensal)
│       └── deploy.yml          # Deploy automático no Vercel
├── data/
│   └── raw/                    # CSVs temporários (gitignored)
├── etl/
│   ├── __init__.py
│   ├── config.py               # URLs ANAC, credenciais via env
│   ├── download.py             # Coleta dos CSVs da ANAC
│   ├── transform_stats.py      # Dados_Estatisticos → schema limpo
│   ├── transform_tarifas.py    # Tarifas_Aereas → schema limpo
│   ├── transform_rab.py        # RAB → schema limpo
│   ├── normalize_empresas.py   # Mapeamento LATAM/TAM/LAN etc.
│   └── load_supabase.py        # Upsert nas tabelas do Supabase
├── sql/
│   ├── schema.sql              # DDL completo das tabelas
│   ├── views_yield.sql         # Views analíticas — Análise A1
│   └── views_frota.sql         # Views analíticas — Análise A4
├── app/                        # Next.js — frontend do dashboard
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx            # Página principal
│   │   ├── yield/
│   │   │   └── page.tsx        # Dashboard A1
│   │   └── frota/
│   │       └── page.tsx        # Dashboard A4
│   ├── components/
│   │   ├── charts/
│   │   │   ├── YieldTimeSeries.tsx
│   │   │   ├── LoadFactorScatter.tsx
│   │   │   ├── FrotaUtilizacao.tsx
│   │   │   └── GaugeEvolution.tsx
│   │   └── ui/
│   │       ├── FilterBar.tsx
│   │       └── MetricCard.tsx
│   ├── lib/
│   │   └── supabase.ts         # Client Supabase (anon key)
│   └── package.json
├── .env.example
├── requirements.txt
├── README.md
└── Makefile
```

---

## II. Fontes de Dados

| Dataset | URL | Formato | Periodicidade | Cobertura |
|---|---|---|---|---|
| Dados Estatísticos | `sistemas.anac.gov.br/dadosabertos/Voos.../Dados_Estatisticos.csv` | CSV `;` | Mensal | 2000–presente |
| Tarifas Domésticas | `sistemas.anac.gov.br/dadosabertos/Voos.../Tarifas_Aereas_Domesticas.csv` | CSV `;` | Trimestral | 2002–presente |
| RAB | `sistemas.anac.gov.br/dadosabertos/Aeronaves/RAB/` | CSV `;` | Snapshot mensal | Corrente |

Todas as fontes são públicas, sem autenticação.

---

## III. Schema do Supabase

### 3.1 Tabelas brutas (staging)

```sql
-- Dados Estatísticos normalizados
CREATE TABLE stg_stats (
    id              BIGSERIAL PRIMARY KEY,
    empresa_sigla   TEXT NOT NULL,
    empresa_nome    TEXT,
    ano             SMALLINT NOT NULL,
    mes             SMALLINT NOT NULL,
    natureza        TEXT,           -- DOMÉSTICA | INTERNACIONAL
    origem_icao     TEXT,
    destino_icao    TEXT,
    passageiros_pagos       INTEGER,
    passageiros_gratis      INTEGER,
    assentos_disponibilizados INTEGER,
    decolagens      INTEGER,
    carga_kg        NUMERIC,
    correio_kg      NUMERIC,
    distancia_km    NUMERIC,
    combustivel_litros NUMERIC,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_sigla, ano, mes, natureza, origem_icao, destino_icao)
);

-- Tarifas Aéreas Domésticas
CREATE TABLE stg_tarifas (
    id              BIGSERIAL PRIMARY KEY,
    empresa_sigla   TEXT NOT NULL,
    ano             SMALLINT NOT NULL,
    mes             SMALLINT NOT NULL,
    trimestre       SMALLINT,
    origem_icao     TEXT,
    destino_icao    TEXT,
    tarifa_media    NUMERIC,        -- R$ médio da passagem
    passageiros     INTEGER,        -- volume vendido no registro
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_sigla, ano, mes, origem_icao, destino_icao)
);

-- RAB — Registro Aeronáutico Brasileiro
CREATE TABLE stg_rab (
    id              BIGSERIAL PRIMARY KEY,
    matricula       TEXT NOT NULL,
    operador        TEXT,
    fabricante      TEXT,
    modelo          TEXT,
    ano_fabricacao  SMALLINT,
    assentos        SMALLINT,
    mtow_kg         INTEGER,
    categoria       TEXT,           -- TPP | TPR | etc.
    situacao        TEXT,           -- ATIVO | CANCELADO
    snapshot_date   DATE NOT NULL,
    UNIQUE (matricula, snapshot_date)
);
```

### 3.2 Tabela de normalização de empresas

```sql
CREATE TABLE dim_empresa (
    sigla_raw       TEXT PRIMARY KEY,   -- como aparece no CSV da ANAC
    sigla_atual     TEXT NOT NULL,      -- sigla canônica
    nome_comercial  TEXT,
    icao            TEXT,
    ativa           BOOLEAN DEFAULT TRUE
);

-- Exemplos de mapeamento necessário:
-- 'TAM'    → 'LATAM'
-- 'LAN'    → 'LATAM'
-- 'WEBJET' → 'GOL'
-- 'VARIG'  → 'VARIG' (inativa)
-- 'TRIP'   → 'AZUL'
```

### 3.3 Views analíticas — Análise A1 (Yield)

```sql
-- Operacional mensal por empresa (doméstico)
CREATE VIEW v_operacional_mensal AS
SELECT
    s.empresa_sigla,
    e.sigla_atual,
    e.nome_comercial,
    s.ano,
    s.mes,
    DATE_TRUNC('month', MAKE_DATE(s.ano, s.mes, 1)) AS periodo,
    SUM(s.passageiros_pagos)            AS pax_pagos,
    SUM(s.assentos_disponibilizados)    AS assentos_totais,
    SUM(s.decolagens)                   AS decolagens,
    SUM(s.passageiros_pagos * s.distancia_km) AS rpk,
    SUM(s.assentos_disponibilizados * s.distancia_km) AS ask,
    CASE WHEN SUM(s.assentos_disponibilizados * s.distancia_km) > 0
        THEN SUM(s.passageiros_pagos * s.distancia_km)::NUMERIC
           / SUM(s.assentos_disponibilizados * s.distancia_km)
        ELSE NULL
    END AS load_factor
FROM stg_stats s
JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
WHERE s.natureza = 'DOMÉSTICA'
GROUP BY 1, 2, 3, 4, 5, 6;

-- Yield e PRASK por empresa (doméstico)
CREATE VIEW v_yield_mensal AS
SELECT
    o.sigla_atual,
    o.nome_comercial,
    o.ano,
    o.mes,
    o.periodo,
    o.load_factor,
    o.rpk,
    o.ask,
    t.receita_total,
    t.pax_tarifas,
    CASE WHEN o.rpk > 0
        THEN t.receita_total / o.rpk
        ELSE NULL
    END AS yield_nominal,                       -- R$/RPK
    CASE WHEN o.ask > 0
        THEN t.receita_total / o.ask
        ELSE NULL
    END AS prask                                -- R$/ASK
FROM v_operacional_mensal o
LEFT JOIN (
    SELECT
        e.sigla_atual,
        t.ano,
        t.mes,
        SUM(t.tarifa_media * t.passageiros) AS receita_total,
        SUM(t.passageiros)                  AS pax_tarifas
    FROM stg_tarifas t
    JOIN dim_empresa e ON t.empresa_sigla = e.sigla_raw
    GROUP BY 1, 2, 3
) t ON o.sigla_atual = t.sigla_atual AND o.ano = t.ano AND o.mes = t.mes;
```

### 3.4 Views analíticas — Análise A4 (Frota)

```sql
-- Frota ativa por empresa-mês via RAB
CREATE VIEW v_frota_ativa AS
SELECT
    r.operador,
    e.sigla_atual,
    e.nome_comercial,
    DATE_TRUNC('month', r.snapshot_date) AS periodo,
    COUNT(DISTINCT r.matricula)          AS aeronaves_ativas,
    AVG(DATE_PART('year', r.snapshot_date) - r.ano_fabricacao) AS idade_media,
    AVG(r.assentos)                      AS assentos_medios,
    STRING_AGG(DISTINCT r.modelo, ', ')  AS modelos
FROM stg_rab r
JOIN dim_empresa e ON r.operador = e.sigla_raw
WHERE r.situacao = 'ATIVO'
    AND r.categoria IN ('TPP', 'TPR')   -- transporte público regular/não regular
GROUP BY 1, 2, 3, 4;

-- Utilização de frota: ASK por aeronave por mês
CREATE VIEW v_utilizacao_frota AS
SELECT
    o.sigla_atual,
    o.nome_comercial,
    o.periodo,
    o.ask,
    o.rpk,
    o.load_factor,
    o.decolagens,
    f.aeronaves_ativas,
    f.idade_media,
    f.assentos_medios,
    CASE WHEN f.aeronaves_ativas > 0
        THEN o.ask / f.aeronaves_ativas
        ELSE NULL
    END AS ask_por_aeronave,
    CASE WHEN f.aeronaves_ativas > 0
        THEN o.decolagens::NUMERIC / f.aeronaves_ativas
        ELSE NULL
    END AS ciclos_por_aeronave,
    CASE WHEN o.decolagens > 0
        THEN o.ask / o.decolagens
        ELSE NULL
    END AS ask_por_decolagem        -- proxy de gauge médio × distância média
FROM v_operacional_mensal o
LEFT JOIN v_frota_ativa f
    ON o.sigla_atual = f.sigla_atual
    AND DATE_TRUNC('month', o.periodo::DATE) = f.periodo;
```

---

## IV. ETL — Pipeline Python

### 4.1 `config.py`

```python
import os

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
ANAC_RAB_URL = (
    "https://sistemas.anac.gov.br/dadosabertos/"
    "Aeronaves/RAB/RelatorioRAB.csv"
)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # service_role key no ETL

EMPRESA_MAP = {
    "TAM": "LATAM",
    "LAN BRASIL": "LATAM",
    "LAN": "LATAM",
    "WEBJET": "GOL",
    "TRIP": "AZUL",
    "OCEAN AIR": "AZUL",
    "PANTANAL": "AZUL",
    "NOAR": "AZUL",
    "VARIG": "VARIG",
    "BRA": "BRA",
    "VOEPASS": "VOEPASS",
    "PASSAREDO": "VOEPASS",
}
```

### 4.2 `transform_stats.py` (lógica principal)

```python
import pandas as pd
from config import EMPRESA_MAP

COLS_MAP = {
    "EMPRESA": "empresa_sigla",
    "EMPRESA (SIGLA)": "empresa_sigla",
    "EMPRESA (Nome)": "empresa_nome",
    "ANO": "ano",
    "MÊS": "mes",
    "NATUREZA": "natureza",
    "AEROPORTO DE ORIGEM": "origem_icao",
    "AEROPORTO DE DESTINO": "destino_icao",
    "PASSAGEIROS PAGOS": "passageiros_pagos",
    "PASSAGEIROS GRÁTIS": "passageiros_gratis",
    "ASSENTOS COMERCIALIZADOS": "assentos_disponibilizados",
    "DECOLAGENS": "decolagens",
    "CARGA PAGA (KG)": "carga_kg",
    "CORREIO (KG)": "correio_kg",
    "DISTÂNCIA VOADA (KM)": "distancia_km",
    "COMBUSTÍVEL (LITROS)": "combustivel_litros",
}

NUMERIC_COLS = [
    "passageiros_pagos", "passageiros_gratis",
    "assentos_disponibilizados", "decolagens",
    "carga_kg", "correio_kg", "distancia_km", "combustivel_litros"
]

def transform(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="utf-8", dtype=str, decimal=",")
    df.columns = df.columns.str.strip()
    df.rename(columns={k: v for k, v in COLS_MAP.items() if k in df.columns}, inplace=True)
    
    # Normalizar empresa
    df["empresa_sigla"] = (
        df["empresa_sigla"].str.strip().str.upper()
        .map(lambda x: EMPRESA_MAP.get(x, x))
    )
    
    # Converter numéricos
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].str.replace(".", "", regex=False)
                                           .str.replace(",", ".", regex=False),
                                    errors="coerce")
    
    df["ano"] = df["ano"].astype("Int16")
    df["mes"] = df["mes"].astype("Int16")
    df = df.dropna(subset=["empresa_sigla", "ano", "mes"])
    
    return df[list(set(COLS_MAP.values()) & set(df.columns))]
```

### 4.3 `load_supabase.py`

```python
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
import pandas as pd

client = create_client(SUPABASE_URL, SUPABASE_KEY)

def upsert_table(df: pd.DataFrame, table: str, chunk_size: int = 1000):
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        client.table(table).upsert(chunk).execute()
        print(f"  [{table}] upserted rows {i}–{i + len(chunk)}")
```

---

## V. GitHub Actions

### 5.1 `.github/workflows/ingest.yml`

```yaml
name: ANAC Data Ingest

on:
  schedule:
    - cron: "0 6 1 * *"   # todo dia 1 do mês às 06h UTC
  workflow_dispatch:        # trigger manual

jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run ETL
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
        run: python etl/run_all.py

      - name: Notify on failure
        if: failure()
        run: echo "ETL falhou — checar logs acima"
```

### 5.2 `requirements.txt`

```
pandas==2.2.2
requests==2.32.3
supabase==2.5.0
python-dotenv==1.0.1
```

---

## VI. Frontend — Next.js no Vercel

### 6.1 Stack

- **Framework:** Next.js 14 (App Router)
- **UI:** Tailwind CSS + shadcn/ui
- **Charts:** Recharts
- **Data:** Supabase JS client (anon key — queries via RLS public)
- **Deploy:** Vercel (conectar repo GitHub, zero config)

### 6.2 `lib/supabase.ts`

```typescript
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);
```

### 6.3 Queries por análise

**Análise A1 — Yield:**
```typescript
// Yield mensal por empresa (últimos 5 anos)
const { data } = await supabase
  .from("v_yield_mensal")
  .select("sigla_atual, nome_comercial, periodo, yield_nominal, prask, load_factor")
  .gte("ano", new Date().getFullYear() - 5)
  .order("periodo", { ascending: true });
```

**Análise A4 — Frota:**
```typescript
// Utilização de frota por empresa
const { data } = await supabase
  .from("v_utilizacao_frota")
  .select("sigla_atual, nome_comercial, periodo, ask_por_aeronave, ciclos_por_aeronave, idade_media, load_factor")
  .gte("periodo", "2018-01-01")
  .order("periodo", { ascending: true });
```

### 6.4 Configuração de RLS no Supabase

```sql
-- Permitir leitura pública das views analíticas (anon key)
ALTER TABLE stg_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE stg_tarifas ENABLE ROW LEVEL SECURITY;
ALTER TABLE stg_rab ENABLE ROW LEVEL SECURITY;

-- Tabelas staging: somente service_role (ETL)
CREATE POLICY "service_only" ON stg_stats
    FOR ALL USING (auth.role() = 'service_role');

-- Views são read-only por padrão; não precisam de RLS adicional
-- mas expor via API requer GRANT:
GRANT SELECT ON v_yield_mensal TO anon;
GRANT SELECT ON v_utilizacao_frota TO anon;
GRANT SELECT ON v_operacional_mensal TO anon;
GRANT SELECT ON dim_empresa TO anon;
```

---

## VII. Variáveis de Ambiente

### `.env.example`

```bash
# ETL (server-side, não expor no frontend)
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Frontend Next.js (público, prefixo NEXT_PUBLIC_)
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

**GitHub Secrets a configurar:**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

**Vercel Environment Variables a configurar:**
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

---

## VIII. Sequência de Setup

```
1. Supabase
   └── Criar projeto
   └── Rodar sql/schema.sql (DDL)
   └── Rodar sql/views_yield.sql
   └── Rodar sql/views_frota.sql
   └── Configurar RLS e GRANTs
   └── Copiar URL + service_role key + anon key

2. ETL local (primeira carga)
   └── cp .env.example .env && preencher
   └── pip install -r requirements.txt
   └── python etl/run_all.py
   └── Verificar contagem nas tabelas

3. GitHub
   └── Criar repositório público
   └── git push
   └── Settings → Secrets → adicionar SUPABASE_URL e SUPABASE_SERVICE_KEY
   └── Actions → rodar ingest.yml manualmente para validar

4. Vercel
   └── Import do repositório GitHub
   └── Root directory: app/
   └── Framework: Next.js (auto-detectado)
   └── Adicionar env vars NEXT_PUBLIC_*
   └── Deploy
```

---

## IX. Checklist de Qualidade dos Dados

Antes de expor no dashboard, validar:

- [ ] Contagem de registros por empresa vs painel ANAC (sanity check)
- [ ] Ausência de duplicatas na `UNIQUE` constraint após upsert
- [ ] Empresas sem match em `dim_empresa` → revisar `normalize_empresas.py`
- [ ] RPK / ASK por empresa bate com publicações ABEAR (±5%)
- [ ] Load Factor doméstico agregado dentro de 65–85% (range histórico normal)
- [ ] RAB: somente aeronaves TPP/TPR ativas (filtrar TAX, privadas)
- [ ] Yield nominal em R$/RPK: range esperado R$ 0.25–0.65 (doméstico atual)
- [ ] Joins RAB × stats: cobertura > 90% das decolagens com match de operador

---

## X. Referências

| Fonte | URL |
|---|---|
| Portal ANAC Dados Abertos | `gov.br/anac/pt-br/acesso-a-informacao/dados-abertos` |
| Base dos Dados (BQ tratado) | `basedosdados.org/dataset/20f3f906-4a8c-4ce3-8274-4da5a76ef560` |
| ABEAR Panorama Setorial | `abear.com.br/publicacoes` |
| Supabase Docs | `supabase.com/docs` |
| Next.js App Router | `nextjs.org/docs/app` |
| Vercel Deploy | `vercel.com/docs/deployments/overview` |

---

<!-- /autoplan restore point: /Users/lucasbarreto/.gstack/projects/anac-analyzer/-autoplan-restore-20260508-204348.md -->

## XI. /autoplan Review Report — 2026-05-08

**Reviewed by:** Claude Subagent (CEO) + Claude Subagent (Design) + Claude Subagent (Eng)
**Codex:** indisponível (binary not found) — single-reviewer mode [subagent-only]
**Escopo UI:** SIM | **Escopo DX:** NÃO

---

### XI.A — Issues Críticos (bloqueiam dados corretos)

#### CRÍTICO 1 — `v_frota_ativa` join sempre vazio (Eng 2.2)
**Problema:** `r.operador = e.sigla_raw` mas RAB usa razão social ("TAM LINHAS AÉREAS S.A."), não sigla ("TAM"). A view A4 retorna zero linhas para todas as empresas.
**Fix:** Adicionar coluna `razao_social TEXT` em `dim_empresa`. Criar mapeamento RAB → sigla em `sql/seed_dim_empresa.sql`. Alterar join para `r.operador = e.razao_social`.

#### CRÍTICO 2 — `stg_tarifas` granularidade trimestral vs. constraint mensal (Eng 2.1 / CEO)
**Problema:** Fonte de tarifas é trimestral, mas schema tem `UNIQUE (empresa_sigla, ano, mes, ...)`. O join em `v_yield_mensal` usa `o.mes = t.mes` — yield será NULL em 8/12 meses se mes derivado do trimestre.
**Fix (confirmado pelo usuário):** Trocar para granularidade trimestral. UNIQUE constraint: `(empresa_sigla, ano, trimestre, origem_icao, destino_icao)`. Join via `CEIL(o.mes::NUMERIC / 3) = t.trimestre`. View de yield passa a ser trimestral.

#### CRÍTICO 3 — `run_all.py` não existe (Eng 1.1)
**Problema:** GitHub Actions chama `python etl/run_all.py` mas o arquivo não está definido no spec. Pipeline falha no primeiro run.
**Fix:** Definir `etl/run_all.py` com orquestração explícita (download → transform → load para cada fonte). Incluir no arquivo o tratamento de erro por fonte (fail-fast vs continue-on-error).

#### CRÍTICO 4 — RLS ausente em `stg_tarifas` e `stg_rab` (Eng 4.1)
**Problema:** RLS habilitado nas tabelas mas sem policies criadas → comportamento deny-all para service_role também (exceto que service_role bypassa RLS, mas o comportamento não está documentado e policies assimétricas são armadilha).
**Fix:** Adicionar `CREATE POLICY "service_only" ON stg_tarifas FOR ALL USING (auth.role() = 'service_role')` e idem para `stg_rab`.

---

### XI.B — Issues Altos

| # | Categoria | Problema | Fix |
|---|---|---|---|
| H1 | Eng | `download.py`, `transform_tarifas.py`, `transform_rab.py` não definidos | Definir com assinaturas e column maps |
| H2 | Eng | `dim_empresa` nunca populada — todas as views retornam zero | Criar `sql/seed_dim_empresa.sql` |
| H3 | Eng | `v_utilizacao_frota` join com cast `::DATE` desnecessário e frágil | Remover cast, joinar direto em `periodo` |
| H4 | Eng | CSV de 400-500MB carregado inteiro na memória | Usar `chunksize=100_000` no pandas |
| H5 | Eng | Workflow re-baixa 25 anos de dados todo mês para ~1 mês novo | Filtrar por `max(ano, mes)` já no banco |
| H6 | Eng | Nenhum teste automatizado — drift silencioso de schema ANAC | Adicionar pytest com contract tests |
| H7 | CEO | Base dos Dados (BigQuery) listada como referência mas nunca avaliada | Parágrafo no README justificando escolha |
| H8 | Design | Hierarquia de informação não definida em nenhuma página | Definir ordem visual para /yield e /frota |
| H9 | Design | Zero estados de UI especificados (loading, empty, error, partial) | Spec de comportamento para cada estado |
| H10 | Design | Homepage `page.tsx` completamente indefinida | Definir como hub de navegação com last-updated |
| H11 | Design | Componentes nomeados mas sem props, eixos ou comportamento | Especificar MetricCards, FilterBar, eixos |
| H12 | Design | `GaugeEvolution` é chart errado para dado de evolução temporal | Substituir por bullet chart ou multi-line |
| H13 | Design | Yield nominal sem disclaimer inflacionário — comparações enganosas | Banner "Valores nominais — sem IPCA" |

---

### XI.C — Issues Médios

| # | Problema | Fix |
|---|---|---|
| M1 | `normalize_empresas.py` duplica `EMPRESA_MAP` de `config.py` | Single source of truth |
| M2 | NULL em colunas de UNIQUE key causa duplicatas no upsert | Sentinel "UNKNOWN" para origem/destino null |
| M3 | Comentário no RLS misrepresenta como views + RLS interagem | Corrigir comentário; considerar SECURITY DEFINER |
| M4 | Natureza doméstica hardcoded — dados internacionais descartados | Fazer `natureza` parâmetro de filtro |
| M5 | Views não materializadas — scan full table a cada query do dashboard | MATERIALIZED VIEW + refresh trigger + índices em (empresa_sigla, ano, mes) |
| M6 | Nenhum indicador de freshness dos dados no dashboard | MetricCard "Dados até: [data]" via MAX(created_at) |
| M7 | FilterBar não especificada — decisões de produto delegadas ao dev | Definir filtros, defaults, URL state para /yield e /frota |
| M8 | Mobile não endereçado | Decisão explícita: desktop-only ≥1024px com declaração no README |

---

### XI.D — Decisão sobre Metodologia de Yield (Premise Gate)

**Confirmado pelo usuário:** `tarifa_media × pax / ASK` é cálculo válido como proxy de PRASK.
**Caveat documentado:** `tarifa_media` da ANAC é tarifa mediana/modal de mercado, não receita contábil auditada. Adicionar nota nos comentários das views e na página do dashboard.

---

### XI.E — Architecture Dependency Graph

```
ANAC URLs (3 fontes)
    │
    ▼
download.py ──────────────────────────────┐
    │                                     │
    ▼                    ▼                ▼
transform_stats.py  transform_tarifas.py  transform_rab.py
    │                    │                │
    ▼                    ▼                ▼
stg_stats           stg_tarifas         stg_rab
    │                    │                │
    └──────────────┬──────┘                │
                   ▼                       │
           v_operacional_mensal            │
           v_yield_mensal ◄─── dim_empresa ◄─── stg_rab
                                               v_frota_ativa
                                               v_utilizacao_frota
                   ▼
           Next.js (anon key) ──► /yield, /frota
           FilterBar ──► queries com parâmetros
```

**Dependência crítica:** `dim_empresa` precisa ser populada ANTES de qualquer view funcionar. É o nó central que conecta ETL → views → dashboard.

---

### XI.F — NOT In Scope (deferred)

- Dados internacionais (natureza ≠ DOMÉSTICA)
- Deflação pelo IPCA (yield real vs nominal)
- Alertas automáticos por Slack/email quando ETL falha
- Autenticação de usuários no dashboard
- Análises além de A1 e A4

---

### XI.G — Decision Audit Trail

| # | Fase | Decisão | Classificação | Princípio | Rationale | Rejeitado |
|---|------|----------|-----------|-----------|----------|---------|
| 1 | CEO | Manter yield como proxy documentado | Mecânica | P3 Pragmatic | Melhor dado público disponível; usuário confirmou | Remover yield |
| 2 | CEO | Agregar tarifas ao nível trimestral | Mecânica | P1 Completeness | Usuário confirmou; preserva granularidade da fonte | Distribuição mensal artificial |
| 3 | CEO | Adicionar parágrafo Base dos Dados no README | Mecânica | P3 Pragmatic | Documenta decisão; custo zero | Ignorar |
| 4 | CEO | Materialized views + índices | Mecânica | P2 Boil Lakes | No blast radius; fix óbvio para performance | Views live sem índices |
| 5 | CEO | MetricCard com data de freshness | Mecânica | P1 Completeness | Dados públicos exigem transparência de latência | Omitir |
| 6 | Eng | Definir run_all.py + demais ETL modules | Mecânica | P1 Completeness | Pipeline não funciona sem eles | |
| 7 | Eng | Adicionar razao_social em dim_empresa | Mecânica | P1 Completeness | Única forma de join funcionar para frota | |
| 8 | Eng | seed_dim_empresa.sql com INSERT inicial | Mecânica | P1 Completeness | Views retornam zero sem dados | |
| 9 | Eng | Trocar join tarifas para trimestre | Mecânica | P1 Completeness | Corrige bug fundamental de yield | Join mensal incorreto |
| 10 | Eng | chunksize=100_000 no pd.read_csv | Mecânica | P2 Boil Lakes | Previne OOM; 5 linhas de código | |
| 11 | Eng | Filtro incremental por max(ano,mes) | Mecânica | P2 Boil Lakes | Reduz 500MB/mês para ~10MB de processamento | Re-download full sempre |
| 12 | Eng | RLS policies para stg_tarifas + stg_rab | Mecânica | P1 Completeness | Simetria de segurança; evita comportamento indefinido | |
| 13 | Eng | pytest + schema contract tests | Mecânica | P1 Completeness | Único mecanismo de detecção de drift silencioso | Checklist manual |
| 14 | Eng | Sentinel "UNKNOWN" para origin/dest nulos | Mecânica | P5 Explicit | PostgreSQL NULL ≠ NULL em UNIQUE — duplicatas silenciosas | |
| 15 | Design | Hierarquia definida: trend line → MetricCards → FilterBar | Mecânica | P5 Explicit | Analistas precisam ver tendência temporal primeiro | |
| 16 | Design | Skeleton + estados vazios/erro por componente | Mecânica | P1 Completeness | Dashboard de dados sem loading state é inutilizável | |
| 17 | Design | GaugeEvolution → bullet chart ou multi-line | Mecânica | P5 Explicit | Gauge não mostra evolução temporal; enganoso para comparar | Manter gauge |
| 18 | Design | Mobile: desktop-only declarado explicitamente | Mecânica | P3 Pragmatic | Dashboard analítico com scatter/time-series não funciona em 375px | Full responsive |
| 19 | Design | Banner "Valores nominais — sem IPCA" | Mecânica | P1 Completeness | Comparação 2008 vs 2024 em R$ nominal é metodologicamente errada sem aviso | |
| 20 | Design | FilterBar spec: período trimestral, multi-select empresas, URL state | Mecânica | P1 Completeness | Sem spec o dev inventa — resultados inconsistentes | |
