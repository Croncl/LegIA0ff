"""
MCP próprio (R8) — Servidor FastMCP que expõe consultar_base.

Uso (na raiz do projeto):
  python src/cgu_rag/agente/mcp_cgu.py

O servidor roda em stdio e pode ser registrado em qualquer cliente MCP
(Claude Desktop, LangChain MCP adapter, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que src/ está no path ao rodar direto
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from mcp.server.fastmcp import FastMCP

from cgu_rag.agente.ferramentas import (
    criar_buscador,
    formatar_trechos,
    trechos_estruturados,
)

mcp = FastMCP(
    name="cgu-rag",
    instructions=(
        "Servidor RAG da CGU. Use consultar_base para buscar trechos nos manuais e "
        "normativos sobre PAD (Processo Administrativo Disciplinar) e PAR "
        "(Processo Administrativo de Responsabilização). "
        "Passe frases curtas com termos técnicos como consulta."
    ),
)

_buscador = criar_buscador()


@mcp.tool()
def consultar_base(consulta: str, k: int = 4) -> dict:
    """Busca trechos nos normativos e manuais da CGU sobre PAD e PAR.

    Args:
        consulta: Frase curta com termos técnicos (prazos, ritos, conceitos jurídicos).
        k: Número de trechos a retornar (padrão 4, máximo 8).

    Returns:
        Dicionário com 'texto' (bloco formatado para o modelo) e
        'trechos' (lista estruturada com doc, páginas e texto).
    """
    k = min(max(1, k), 8)
    linhas = _buscador(consulta, k)
    return {
        "texto": formatar_trechos(linhas),
        "trechos": trechos_estruturados(linhas),
    }


if __name__ == "__main__":
    mcp.run()
