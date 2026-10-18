#!/usr/bin/env bash
# setup.sh — Configuração e inicialização completa do ANAC Aviation Analytics
#
# Uso: ./setup.sh
#
# Etapas:
#   1. Validação de ferramentas (Python 3.11+, Bun/Node, JQ)
#   2. Criação do virtualenv (.venv) e instalação de dependências Python
#   3. Instalação de dependências do frontend Next.js (app/)
#   4. Configuração de arquivos .env e app/.env.local
#   5. Aplicação do DDL, seeds de empresas e views analíticas no banco
#   6. Registro do MCP Server (anac-analyzer) no ~/.claude.json
#   7. Verificação de integridade da base e teste de leitura

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[setup]${NC} $*"; }
warn()  { echo -e "${YELLOW}[aviso]${NC} $*"; }
error() { echo -e "${RED}[erro]${NC}  $*" >&2; }

echo "══════════════════════════════════════════════════════════════════════"
echo "  ANAC Aviation Analytics — Inicialização do Ambiente"
echo "══════════════════════════════════════════════════════════════════════"

# ── 1. Dependências do Sistema ──────────────────────────────────────────────
info "1/7 Verificando ferramentas do sistema..."

if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
elif command -v uv &>/dev/null; then
    PYTHON="uv run python"
else
    error "Python 3 não encontrado. Instale Python 3.11+ e tente novamente."
    exit 1
fi
info "Python: $($PYTHON --version)"

# Bun ou Node/NPM
if command -v bun &>/dev/null; then
    JS_RUNNER="bun"
    info "JavaScript runtime: Bun ($(bun --version))"
elif command -v npm &>/dev/null; then
    JS_RUNNER="npm"
    info "JavaScript runtime: Node/NPM ($(node --version))"
else
    warn "Nem Bun nem NPM encontrados. Frontend dashboard não será buildado automaticamente."
    JS_RUNNER=""
fi

# JQ
if command -v jq &>/dev/null; then
    JQ_AVAILABLE=true
else
    warn "jq não encontrado. Configuração de MCP automática será via Python."
    JQ_AVAILABLE=false
fi

# ── 2. Virtualenv Python ───────────────────────────────────────────────────
info "2/7 Configurando ambiente virtual Python (.venv)..."
if [ ! -d ".venv" ]; then
    if command -v uv &>/dev/null; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

VENV_PY="$REPO_DIR/.venv/bin/python"
VENV_PIP="$REPO_DIR/.venv/bin/pip"

info "Instalando dependências Python (requirements.txt + dev)..."
if command -v uv &>/dev/null; then
    uv pip install -q -r requirements.txt -r requirements-dev.txt
else
    "$VENV_PIP" install -q --upgrade pip
    "$VENV_PIP" install -q -r requirements.txt -r requirements-dev.txt
fi

# ── 3. Dependências do Frontend ────────────────────────────────────────────
info "3/7 Instalando dependências do Next.js (app/)..."
if [ -n "$JS_RUNNER" ]; then
    (cd app && $JS_RUNNER install --silent)
fi

# ── 4. Configuração de Variáveis de Ambiente ───────────────────────────────
info "4/7 Configurando variáveis de ambiente (.env e app/.env.local)..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn "Arquivo .env criado a partir de .env.example. Verifique a DATABASE_URL."
    else
        error ".env não encontrado e .env.example inexistente."
        exit 1
    fi
fi

if [ ! -f "app/.env.local" ]; then
    cp .env app/.env.local
    info "app/.env.local sincronizado com .env"
fi

# ── 5. Inicialização e Migrações do Banco ──────────────────────────────────
info "5/7 Inicializando esquema de banco e views analíticas..."
"$VENV_PY" - << 'PYEOF'
import psycopg2, os
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("  AVISO: DATABASE_URL não definida, pulando inicialização DDL.")
    exit(0)

conn = psycopg2.connect(db_url)
conn.autocommit = True
sql_files = [
    "sql/schema.sql",
    "sql/seed_dim_empresa.sql",
    "sql/views_yield.sql",
    "sql/views_frota.sql",
]
with conn.cursor() as cur:
    for fpath in sql_files:
        with open(fpath, "r", encoding="utf-8") as f:
            cur.execute(f.read())
print("  Esquema, dim_empresa e views materializadas aplicados com sucesso.")
PYEOF

# ── 6. Registro do MCP Server no ~/.claude.json ─────────────────────────────
info "6/7 Registrando servidor MCP anac-analyzer..."
"$VENV_PY" - << 'PYEOF'
import json, os
from pathlib import Path

claude_json_path = Path.home() / ".claude.json"
data = {}
if claude_json_path.exists():
    try:
        with open(claude_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

mcp_servers = data.setdefault("mcpServers", {})
repo = str(Path(".").resolve())
mcp_servers["anac-analyzer"] = {
    "command": f"{repo}/.venv/bin/python",
    "args": [f"{repo}/scripts/mcp/anac_mcp.py"],
    "env": {
        "DATABASE_URL": os.environ.get("DATABASE_URL", "")
    }
}

with open(claude_json_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("  MCP anac-analyzer configurado em ~/.claude.json")
PYEOF

# ── 7. Verificação de Integridade ──────────────────────────────────────────
info "7/7 Executando verificação de integridade da base..."
"$VENV_PY" scripts/check_integrity.py

echo ""
echo "──────────────────────────────────────────────────────────────────────"
info "Setup do ANAC Aviation Analytics concluído com sucesso!"
echo ""
echo "Comandos disponíveis:"
echo "  make check       # Verificação detalhada de integridade da base"
echo "  make eval        # Benchmark de qualidade de leitura por LLM e MCP"
echo "  make test        # Bateria completa de testes automatizados (pytest)"
echo "  make etl         # Rodar ingestão e atualização incremental"
echo "  make dev         # Iniciar dashboard Next.js localmente"
echo "──────────────────────────────────────────────────────────────────────"

