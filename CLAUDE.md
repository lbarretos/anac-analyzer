# ANAC Aviation Analytics — Guia de Instruções para Agentes e LLMs

Base analítica de dados da aviação civil brasileira (ANAC), integrada com Neon PostgreSQL, servidor MCP e dashboard Next.js.

---

## 🔐 Coordenadas de Conexão Somente-Leitura (Read-Only)

Para conectar LLMs, agentes, LangChain ou ferramentas BI à base com segurança (apenas comandos `SELECT` são aceitos):

- **Host:** `ep-raspy-flower-ap8igjra-pooler.c-7.us-east-1.aws.neon.tech`
- **Porta:** `5432`
- **Database:** `anac_db`
- **Usuário:** `anac_ro`
- **Senha:** *(definida no ambiente local `.env` / `/Users/Shared/neon-anac.txt`)*
- **SSL:** `require`

### Padrão de Connection String:
```text
postgresql://anac_ro:<SENHA>@ep-raspy-flower-ap8igjra-pooler.c-7.us-east-1.aws.neon.tech/anac_db?sslmode=require&channel_binding=require
```

> **Atenção:** As credenciais completas ficam armazenadas localmente no seu arquivo `.env` (gitignored), no `~/.claude.json` e no arquivo local seguro `/Users/Shared/neon-anac.txt`. Nunca versione credenciais no git.

---

## 🤖 Conexão via Servidor MCP (`anac-analyzer`)

O servidor MCP já está configurado no seu ambiente local em `~/.claude.json`. Para clientes de IA (Claude Code, Antigravity, Cursor, Claude Desktop), utilize o seguinte bloco (as credenciais são lidas da variável de ambiente):

```json
{
  "mcpServers": {
    "anac-analyzer": {
      "command": "/Users/lucasbarreto/Documents/anac-analyzer/.venv/bin/python",
      "args": ["/Users/lucasbarreto/Documents/anac-analyzer/scripts/mcp/anac_mcp.py"],
      "env": {
        "DATABASE_URL": "postgresql://anac_ro:<SENHA>@ep-raspy-flower-ap8igjra-pooler.c-7.us-east-1.aws.neon.tech/anac_db?sslmode=require&channel_binding=require"
      }
    }
  }
}
```


---

## 📊 Estrutura e Regras de Negócio para o LLM

Ao formular análises e consultas SQL, observe as seguintes diretrizes metodológicas:

1. **Granularidade do Yield:** As tarifas aéreas coletadas pela ANAC são publicadas em frequência **trimestral**. Por esse motivo, as métricas de *Yield Nominal* (R$/RPK) e *PRASK* (R$/ASK) estão consolidadas na view [`v_yield_trimestral`](file:///Users/lucasbarreto/Documents/anac-analyzer/sql/views_yield.sql). Não existe yield mensal no banco.
2. **Normalização de Companhias:** Sempre priorize o campo `sigla_atual` (ex: `LATAM`, `GOL`, `AZUL`, `VOEPASS`, `MAP`). Siglas antigas como `TAM`, `WEBJET` ou `TRIP` estão normalizadas via [`dim_empresa`](file:///Users/lucasbarreto/Documents/anac-analyzer/sql/seed_dim_empresa.sql).
3. **Aeronaves Comerciais (RAB):** A view [`v_frota_ativa`](file:///Users/lucasbarreto/Documents/anac-analyzer/sql/views_frota.sql) filtra estritamente aeronaves ativas em transporte comercial regular/não regular (`RBAC 121` e `RBAC 135`) no snapshot mais recente.
4. **Cálculo de Load Factor:** O aproveitamento de assentos é $RPK / ASK$ ponderado pela distância média dos voos com decolagem ($decolagens > 0$).

---

## 🛠️ Comandos Principais

```bash
make check     # Audita a integridade estrutural e sanidade de domínio aeronáutico
make eval      # Roda o benchmark golden de acurácia de leitura por LLM e MCP
make test      # Executa suíte com 23 testes automatizados via pytest
make mcp       # Inicia o servidor MCP localmente
make dev       # Inicia o dashboard Next.js local em http://localhost:3000
```

