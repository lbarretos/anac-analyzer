# ANAC Aviation Analytics

Pipeline analítico de aviação civil brasileira com ingestão de dados abertos da ANAC, armazenamento em **PostgreSQL (Neon)**, **servidor MCP (Model Context Protocol)** para LLMs e agentes de IA, e dashboard interativo em **Next.js**.

---

## 🛫 Análises no Escopo

- **A1 — Yield Real e PRASK Implícito** (`stg_stats` × `stg_tarifas`): R$/RPK e R$/ASK por companhia em granularidade trimestral.
- **A2 — Volume Mensal de Tráfego** (`stg_stats`): Passageiros pagos, assentos ofertados, decolagens, RPK, ASK e *Load Factor*.
- **A4 — Utilização de Frota e Produtividade** (`stg_stats` × `stg_rab`): ASK/aeronave, ciclos/aeronave e idade média da frota.

---

## 🏗️ Arquitetura

```
Fontes ANAC (Públicas)
  ├── Dados Estatísticos (CSV mensal, 343 MB)
  ├── Tarifas Domésticas SAS (CSV por mês/ano)
  └── Registro Aeronáutico Brasileiro (RAB, snapshot mensal)
          │
          ▼
     ETL Python (.venv)
  ├── etl/download.py           # Download com retry e validação
  ├── etl/transform_stats.py    # Limpeza, deduplicação e agregação por rota
  ├── etl/transform_tarifas.py  # Ponderação de tarifas médias por trimestre
  ├── etl/transform_rab.py      # Filtro de frotas comerciais (RBAC 121 / 135)
  └── etl/load_supabase.py      # Carga idempotente via psycopg2 / Neon HTTP
          │
          ▼
Neon PostgreSQL (anac_db)
  ├── Tabelas Staging: stg_stats, stg_tarifas, stg_rab, dim_empresa
  └── Views Materializadas:
        ├── v_operacional_mensal
        ├── v_yield_trimestral
        ├── v_frota_ativa
        └── v_utilizacao_frota
          │
          ├─────────────────────────────────────────┐
          ▼                                         ▼
   Servidor MCP (scripts/mcp/)               Next.js App Router (app/)
   Acesso conversacional para LLMs           Dashboard analítico online
   (Claude Code, Antigravity, Cursor)        (Recharts + Tailwind CSS)
```

---

## 🚀 Setup Rápido (1 Comando)

Execute o script de automação para preparar o ambiente virtual, instalar dependências, aplicar o esquema no banco e registrar o MCP:

```bash
./setup.sh
```

Ou via Makefile:

```bash
make setup
```

---

## 🛡️ Verificação de Integridade da Base

O script [`scripts/check_integrity.py`](file:///Users/lucasbarreto/Documents/anac-analyzer/scripts/check_integrity.py) audita a integridade estrutural e a sanidade de domínio aeronáutico:

```bash
make check
# ou: .venv/bin/python scripts/check_integrity.py
```

### O que é verificado:
1. **Volumetria & Freshness**: contagem de linhas e períodos mais recentes em cada tabela.
2. **Restrições de Unicidade**: ausência absoluta de chaves duplicadas em `stg_stats`, `stg_tarifas` e `stg_rab`.
3. **Validação de Nulos**: campos críticos (`empresa_sigla`, `ano`, `mes`, `natureza`) 100% preenchidos.
4. **Cobertura Dimensional**: >90% das operações domésticas mapeadas para siglas canônicas em `dim_empresa`.
5. **Join de Frota RAB**: correspondência das razões sociais com operadoras comerciais ativas.
6. **Sanidade Estatística**:
   - *Load Factor* no intervalo esperado [0, 1] com média histórica entre 65% e 85%.
   - Consistência física $RPK \le ASK$.
   - Tarifas médias em patamares realistas de mercado (R$ 50 a R$ 5.000).
   - *Yield Nominal* em faixa condizente (R$ 0.05 a R$ 0.80 / RPK).
   - Idade média da frota e assentos médios coerentes por aeronave.

---

## 🤖 Servidor MCP (Model Context Protocol)

O servidor MCP [`scripts/mcp/anac_mcp.py`](file:///Users/lucasbarreto/Documents/anac-analyzer/scripts/mcp/anac_mcp.py) permite que LLMs consultem a base de dados com segurança:

- **Modo padrão:** `stdio` (iniciado sob demanda por Claude Code, Claude Desktop, Antigravity).
- **Modo HTTP:** `python scripts/mcp/anac_mcp.py --http --port 8766`

### Ferramentas Expostas:
| Ferramenta | Descrição |
|---|---|
| `query(sql)` | Executa consulta SQL SELECT ad-hoc com timeout (20s) e sanitização de escrita. |
| `list_tables()` | Catálogo de tabelas e views analíticas com contagens de linhas. |
| `describe_table(table_name)` | Esquema de colunas, tipos de dados e amostra da tabela. |
| `resolve_airline(query)` | Mapeia siglas históricas (`TAM`, `WEBJET`, `TRIP`) para operadoras canônicas (`LATAM`, `GOL`, `AZUL`). |
| `get_yield_metrics(...)` | Indicadores trimestrais de Yield nominal (R$/RPK), PRASK (R$/ASK) e receita proxy. |
| `get_fleet_metrics(...)` | Número de aeronaves ativas, idade média, assentos médios e modelos do RAB. |
| `get_fleet_utilization(...)` | Indicadores de produtividade: ASK por aeronave e ciclos por aeronave. |
| `get_traffic_volume(...)` | Tráfego mensal: passageiros pagos, assentos, decolagens, RPK, ASK e load factor. |
| `check_data_integrity()` | Relatório estruturado de saúde e qualidade da base. |

### Configuração no Claude (`~/.claude.json`):
```json
{
  "mcpServers": {
    "anac-analyzer": {
      "command": "/Users/lucasbarreto/Documents/anac-analyzer/.venv/bin/python",
      "args": ["/Users/lucasbarreto/Documents/anac-analyzer/scripts/mcp/anac_mcp.py"],
      "env": {
        "DATABASE_URL": "postgresql://..."
      }
    }
  }
}
```

---

## 🎯 Teste de Qualidade da Leitura por LLM e MCP

O benchmark [`scripts/eval/eval_llm.py`](file:///Users/lucasbarreto/Documents/anac-analyzer/scripts/eval/eval_llm.py) avalia a precisão das ferramentas MCP contra o conjunto golden de 10 perguntas analíticas calibradas ([`scripts/eval/golden_dataset.json`](file:///Users/lucasbarreto/Documents/anac-analyzer/scripts/eval/golden_dataset.json)):

```bash
make eval
# ou: .venv/bin/python scripts/eval/eval_llm.py
```

### Resultados do Benchmark Golden:
- **Acurácia:** 10/10 (100.0%)
- **Latência Média:** ~2.1 s
- **Tamanho Médio de Resposta:** 953 caracteres (economia >95% do contexto do LLM)
- **Cobertura de Casos:**
  - Extração pontual (Frota da Azul: 372 aeronaves, 12.3 anos)
  - Métricas operacionais (Load Factor LATAM jul/2026: 85.38%)
  - Séries de Yield (Yield GOL 4T24: R$ 0.1767/RPK)
  - Agregações anuais (Total de passageiros pagos em 2024: 93.499.821)
  - Comparativos de frota (Frota mais jovem: Azul com 12.3 anos)
  - Produtividade (Ciclos por aeronave GOL ago/2026: 64.0)
  - Resolução de siglas históricas (TAM → LATAM, Webjet → GOL)
  - Armadilhas metodológicas (Granularidade trimestral do yield)
  - Armadilhas negativas (Varig: 0 aeronaves ativas no snapshot atual)

---

## 🧪 Testes Automatizados

Rode a suíte completa de 23 testes automatizados via pytest:

```bash
make test
```

Inclui:
- `tests/test_transform_stats.py`: Contrato e transformações de dados estatísticos.
- `tests/test_transform_tarifas.py`: Parsers decimais e agregação trimestral de tarifas.
- `tests/test_data_integrity.py`: Auditoria contínua de integridade do banco de dados.
- `tests/test_mcp_llm_quality.py`: Validação de contrato e assertividade do servidor MCP.

---

## 📊 Dashboard Web (Next.js)

```bash
# Desenvolvimento
make dev

# Build de produção
make build
```

Acesse em `http://localhost:3000` para navegar pelas visualizações:
- `/` — Visão geral e cartões de acesso
- `/yield` — Análise A1 (Yield nominal e PRASK)
- `/volume` — Análise A2 (Volume mensal de passageiros e assentos)
- `/frota` — Análise A4 (Utilização de frota e ASK por aeronave)

