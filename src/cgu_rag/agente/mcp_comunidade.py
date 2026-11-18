"""
MCPs da comunidade (R9) — fetch e DuckDuckGo Search.

Expõe duas ferramentas LangChain que o grafo pode usar ao lado de consultar_base:
  - buscar_web(consulta)   → DuckDuckGo: retorna URLs e snippets relevantes
  - buscar_url(url)        → fetch: lê o conteúdo de uma URL (Diário Oficial, LegisWeb, etc.)

Uso no grafo (em criar_grafo):
  from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web
  ferramentas = [consultar_base] + criar_ferramentas_web()
  grafo = criar_grafo(modelo, ferramentas=ferramentas)
"""
from __future__ import annotations

from langchain_core.tools import tool


def criar_ferramentas_web() -> list:
    """Retorna [buscar_web, buscar_url] prontas para o grafo."""
    return [buscar_web, buscar_url]


@tool
def buscar_web(consulta: str) -> str:
    """Busca na web via DuckDuckGo. Use para encontrar normas, portarias ou
    notícias recentes sobre PAD, PAR e legislação federal que não estejam
    no corpus local. Retorna títulos, URLs e snippets dos resultados.

    Args:
        consulta: Termos de busca em português (ex: 'instrução normativa CGU 2024').
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddg:
            resultados = list(ddg.text(consulta, max_results=5))
        if not resultados:
            return "Nenhum resultado encontrado."
        linhas = []
        for i, r in enumerate(resultados, 1):
            linhas.append(f"[{i}] {r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')[:300]}")
        return "\n\n".join(linhas)
    except Exception as e:
        return f"Erro na busca web: {e}"


@tool
def buscar_url(url: str) -> str:
    """Lê o conteúdo de uma URL (Diário Oficial, LegisWeb, CGU, Planalto).
    Use após buscar_web para ler o texto completo de uma norma ou portaria.
    Retorna os primeiros 2000 caracteres do conteúdo.

    Args:
        url: URL completa (https://...).
    """
    try:
        import urllib.request
        import urllib.error
        from html.parser import HTMLParser

        class _Extrator(HTMLParser):
            def __init__(self):
                super().__init__()
                self._capturar = True
                self._blocos: list[str] = []
                self._ignorar = {"script", "style", "nav", "header", "footer"}
                self._pilha: list[str] = []

            def handle_starttag(self, tag, attrs):
                self._pilha.append(tag)
                if tag in self._ignorar:
                    self._capturar = False

            def handle_endtag(self, tag):
                if self._pilha and self._pilha[-1] == tag:
                    self._pilha.pop()
                if tag in self._ignorar:
                    self._capturar = True

            def handle_data(self, data):
                if self._capturar:
                    t = data.strip()
                    if t:
                        self._blocos.append(t)

            def texto(self) -> str:
                return " ".join(self._blocos)

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        extrator = _Extrator()
        extrator.feed(html)
        texto = extrator.texto()[:2000]
        return texto or "[Conteúdo não extraível]"
    except Exception as e:
        return f"Erro ao buscar URL: {e}"
