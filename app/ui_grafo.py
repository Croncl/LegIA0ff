"""
Mapa de Conhecimento dinâmico.
Constrói um grafo interativo a partir das palavras mais relevantes
das mensagens do chat, renderizado via pyvis + streamlit.components.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

import networkx as nx
import streamlit as st
 
# import streamlit.components.v1 as components - DEPRECADO      

import base64
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Stopwords (português + inglês + termos técnicos curtos)
# ---------------------------------------------------------------------------
STOPWORDS = {
    # PT
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "e", "é", "em",
    "um", "uma", "uns", "umas", "para", "por", "com", "sem", "sob", "sobre",
    "ao", "à", "aos", "às", "que", "quem", "qual", "quais", "cujo", "cuja",
    "se", "ser", "foi", "são", "era", "tem", "ter", "há", "houve", "não",
    "sim", "mais", "menos", "muito", "pouco", "também", "já", "ainda",
    "como", "quando", "onde", "porque", "pois", "mas", "porém", "todavia",
    "então", "assim", "desta", "deste", "dessa", "desse", "destas", "destes",
    "nessa", "nesse", "neste", "nesta", "suas", "seus", "meu", "minha",
    "teu", "tua", "nosso", "nossa", "isso", "isto", "aquilo", "ele", "ela",
    "eles", "elas", "nós", "eu", "você", "vocês", "sim", "não", "ok",
    "obrigado", "obrigada", "valeu", "bom", "boa", "mau", "má","pág", "págs", "voltado",
    "trata","tratam","entre"
    # EN
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "this", "that", "these", "those", "it", "its", "i", "you", "he", "she",
    "we", "they", "them", "their", "our", "my", "your", "and", "or", "but",
    "if", "then", "so", "as", "not", "no", "yes",
}

# Regex: captura palavras com 3+ letras (inclui acentos)
_REGEX = re.compile(r"\b[^\W\d_]{3,}\b", re.UNICODE)


# ---------------------------------------------------------------------------
# Extração de palavras-chave
# ---------------------------------------------------------------------------
def _tokenizar(texto: str) -> list[str]:
    """Tokeniza e filtra stopwords."""
    tokens = _REGEX.findall(texto.lower())
    return [t for t in tokens if t not in STOPWORDS]


def extrair_palavras_relevantes(
    mensagens: Iterable[dict],
    top_n: int = 40,
    janela: int = 3,
) -> tuple[list[str], list[tuple[str, str, int]]]:
    """
    Retorna (nós, arestas) a partir das mensagens.
    - Nós: palavras mais frequentes (top_n).
    - Arestas: co-ocorrência dentro de uma janela de `janela` tokens.
    """
    contador_palavras: Counter[str] = Counter()
    contador_pares: Counter[tuple[str, str]] = Counter()

    for msg in mensagens:
        tokens = _tokenizar(msg.get("texto", ""))
        contador_palavras.update(tokens)
        # co-ocorrência em janela
        for i, t1 in enumerate(tokens):
            for t2 in tokens[i + 1 : i + 1 + janela]:
                if t1 != t2:
                    par = tuple(sorted((t1, t2)))
                    contador_pares[par] += 1

    # Top palavras
    top_palavras = [p for p, _ in contador_palavras.most_common(top_n)]
    conjunto_top = set(top_palavras)

    # Arestas apenas entre top palavras
    arestas = [
        (a, b, peso)
        for (a, b), peso in contador_pares.items()
        if a in conjunto_top and b in conjunto_top
    ]
    return top_palavras, arestas


# ---------------------------------------------------------------------------
# Construção e renderização do grafo
# ---------------------------------------------------------------------------
def _construir_grafo_pyvis(
    nos: list[str],
    arestas: list[tuple[str, str, int]],
    freq: dict[str, int],
) -> str:
    """Constrói o grafo pyvis e retorna HTML."""
    from pyvis.network import Network

    net = Network(
        height="420px",
        width="100%",
        bgcolor="#0F1419",
        font_color="#E6EDF3",
        directed=False,
        notebook=False,
    )
    net.barnes_hut(
        gravity=-3500,
        central_gravity=0.3,
        spring_length=120,
        spring_strength=0.05,
        damping=0.09,
        overlap=0,
    )

    if not nos:
        net.add_node("vazio", label="Faça perguntas para construir o mapa",
                     color="#2A3441", font={"size": 18, "color": "#8B949E"})
        return net.generate_html()

    max_freq = max(freq.values()) if freq else 1

    # Nós
    for n in nos:
        f = freq.get(n, 1)
        tamanho = 15 + int(25 * (f / max_freq))
        net.add_node(
            n,
            label=n,
            size=tamanho,
            color={
                "background": "#F59E0B",
                "border": "#FCD34D",
                "highlight": {"background": "#06B6D4", "border": "#67E8F9"},
            },
            font={"size": max(12, tamanho // 2), "face": "Inter", "color": "#E6EDF3"},
            title=f"<b>{n}</b><br>Ocorrências: {f}",
        )

    # Arestas
    max_peso = max((p for _, _, p in arestas), default=1)
    for a, b, p in arestas:
        largura = 0.5 + 3.5 * (p / max_peso)
        net.add_edge(
            a, b,
            value=p,
            width=largura,
            color={"color": "#2A4A70", "opacity": 0.7},
            title=f"Co-ocorrências: {p}",
        )

    # Remove toolbar/physics controls (visual limpo)
    net.set_options("""
    {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -3500,
          "centralGravity": 0.3,
          "springLength": 120,
          "springConstant": 0.05,
          "damping": 0.09
        },
        "stabilization": {"iterations": 150}
      },
      "interaction": {"hover": true, "tooltipDelay": 200},
      "edges": {"smooth": {"type": "continuous"}}
    }
    """)
    return net.generate_html()


def _html_para_iframe(html: str, height: int = 440) -> None:
    """Renderiza HTML via iframe embutido com data URL (sem dependência de components.v1)."""
    # Codifica o HTML em base64 para uso em data URL
    html_b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    data_url = f"data:text/html;charset=utf-8;base64,{html_b64}"

    # Iframe inline via st.markdown — sem classes internas, sem warnings
    st.markdown(
        f"""
        <iframe
            src="{data_url}"
            style="width:100%; height:{height}px; border:1px solid var(--cg-border, #2A3441);
                   border-radius:12px; background:#0F1419;"
            loading="lazy"
        ></iframe>
        """,
        unsafe_allow_html=True,
    )


def renderizar_mapa_conhecimento(mensagens: list[dict], top_n: int = 40) -> None:
    """Renderiza o mapa de conhecimento na coluna principal."""
    nos, arestas = extrair_palavras_relevantes(mensagens, top_n=top_n)

    # Calcula frequência para tamanho dos nós
    freq: dict[str, int] = {}
    for msg in mensagens:
        for t in _tokenizar(msg.get("texto", "")):
            freq[t] = freq.get(t, 0) + 1
    freq_top = {n: freq.get(n, 1) for n in nos}

    html = _construir_grafo_pyvis(nos, arestas, freq_top)

    with st.expander(
        f"🧠 Mapa de Conhecimento ({len(nos)} conceitos · {len(arestas)} conexões)",
        expanded=False,
    ):
        st.caption(
            "Cada nó é uma palavra-chave recorrente nas mensagens. "
            "Arestas conectam termos que aparecem juntos. Arraste os nós para explorar."
        )
        # antes:
        # components.html(html, height=440, scrolling=False)

        # depois:
        _html_para_iframe(html, height=440)
