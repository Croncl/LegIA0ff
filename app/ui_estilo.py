"""
Camada visual do Assistente CGU.
Centraliza: tema CSS, componentes reutilizáveis (cabeçalho, sidebar,
badges de ferramentas, renderização de mensagens e detalhes de execução).
Não depende de classes internas instáveis do Streamlit.
"""
from __future__ import annotations

import json
from typing import Iterable

import streamlit as st

# ---------------------------------------------------------------------------
# Paleta e tokens de design
# ---------------------------------------------------------------------------
TEMA = {
    "bg": "#0F1419",
    "bg_elev": "#151B23",
    "bg_card": "#1A212B",
    "border": "#2A3441",
    "border_soft": "#1F2731",
    "text": "#E6EDF3",
    "text_muted": "#8B949E",
    "text_dim": "#6E7681",
    "accent": "#F59E0B",       # âmbar — destaque primário (jurídico/CGU)
    "accent_soft": "#FCD34D",
    "accent_cyan": "#06B6D4",  # destaque secundário
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "user_bubble": "#1E3A5F",
    "assistant_bubble": "#1A212B",
}

EMOJIS = {
    "consultar_base": "🔍",
    "buscar_web": "🌐",
    "buscar_url": "🔗",
    "resumir_trecho": "📝",
    "filtro_prompt": "🛡️",
    "transparencia_sancoes": "⚖️",
    "transparencia_pep": "👤",
    "transparencia_despesas_favorecido": "💰",
    "transparencia_despesas_documentos": "📄",
    "cnpj_consultar": "🏢",
    "cnpj_processos": "⚖️",
}

# ---------------------------------------------------------------------------
# CSS global (injetado via st.markdown)
# ---------------------------------------------------------------------------
_CSS_GLOBAL = f"""
<style>
:root {{
    --cg-bg: {TEMA["bg"]};
    --cg-bg-elev: {TEMA["bg_elev"]};
    --cg-bg-card: {TEMA["bg_card"]};
    --cg-border: {TEMA["border"]};
    --cg-border-soft: {TEMA["border_soft"]};
    --cg-text: {TEMA["text"]};
    --cg-text-muted: {TEMA["text_muted"]};
    --cg-text-dim: {TEMA["text_dim"]};
    --cg-accent: {TEMA["accent"]};
    --cg-accent-soft: {TEMA["accent_soft"]};
    --cg-accent-cyan: {TEMA["accent_cyan"]};
    --cg-success: {TEMA["success"]};
    --cg-warning: {TEMA["warning"]};
    --cg-danger: {TEMA["danger"]};
}}

/* ---------- Base ---------- */
html, body, [class*="css"] {{
    color: var(--cg-text);
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}}
.stApp {{
    background: radial-gradient(1200px 600px at 10% -10%, #162030 0%, var(--cg-bg) 55%) fixed;
}}
header[data-testid="stHeader"] {{
    background: rgba(15, 20, 25, 0.75);
    backdrop-filter: blur(8px);
}}

/* ---------- Tipografia ---------- */
h1, h2, h3, h4 {{
    color: var(--cg-text);
    letter-spacing: -0.01em;
}}
h1 {{
    background: linear-gradient(90deg, var(--cg-accent-soft), var(--cg-accent));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 700;
}}
p, li, span, label {{
    color: var(--cg-text);
}}
code, pre {{
    background: var(--cg-bg-elev) !important;
    color: var(--cg-accent-soft) !important;
    border: 1px solid var(--cg-border-soft);
    border-radius: 6px;
}}

/* ---------- Chat bubbles ---------- */
.stChatMessage {{
    background: transparent !important;
}}
div[data-testid="stChatMessage"] {{
    background: var(--cg-bg-card);
    border: 1px solid var(--cg-border);
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: 0 1px 0 rgba(255,255,255,0.02) inset;
}}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    border-color: #2A4A70;
    background: linear-gradient(180deg, #1E3A5F 0%, #172B45 100%);
}}

/* ---------- Inputs ---------- */
.stTextInput input, .stChatInput textarea, .stChatInputContainer {{
    background: var(--cg-bg-elev) !important;
    border: 1px solid var(--cg-border) !important;
    color: var(--cg-text) !important;
    border-radius: 12px !important;
}}
.stTextInput input:focus, .stChatInput textarea:focus {{
    border-color: var(--cg-accent) !important;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.18) !important;
}}

/* ---------- Botões ---------- */
.stButton > button {{
    background: var(--cg-bg-card);
    color: var(--cg-text);
    border: 1px solid var(--cg-border);
    border-radius: 10px;
    transition: all 0.18s ease;
    font-weight: 500;
}}
.stButton > button:hover {{
    border-color: var(--cg-accent);
    color: var(--cg-accent-soft);
    transform: translateY(-1px);
}}
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, var(--cg-accent), #D97706);
    color: #0F1419;
    border: none;
    font-weight: 600;
}}

/* ---------- Expander (detalhes) ---------- */
.streamlit-expanderHeader {{
    background: var(--cg-bg-elev);
    border: 1px solid var(--cg-border-soft);
    border-radius: 10px;
    color: var(--cg-text-muted);
    font-size: 0.9rem;
}}
.streamlit-expanderHeader:hover {{
    color: var(--cg-accent-soft);
    border-color: var(--cg-border);
}}
.streamlit-expanderContent {{
    background: var(--cg-bg-elev);
    border: 1px solid var(--cg-border-soft);
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 12px 14px;
}}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0B1016 0%, #0F1419 100%);
    border-right: 1px solid var(--cg-border-soft);
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: var(--cg-text);
}}

/* ---------- Dividers ---------- */
hr {{
    border-color: var(--cg-border-soft) !important;
    margin: 14px 0;
}}

/* ---------- Scrollbars ---------- */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: var(--cg-bg); }}
::-webkit-scrollbar-thumb {{
    background: var(--cg-border);
    border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{ background: var(--cg-text-dim); }}

/* ---------- Componentes customizados (badges, cards) ---------- */
.cg-cabecalho {{
    padding: 10px 14px;
    border-left: 3px solid var(--cg-accent);
    background: linear-gradient(90deg, rgba(245,158,11,0.08), transparent);
    border-radius: 0 10px 10px 0;
    margin-bottom: 18px;
}}
.cg-cabecalho h1 {{ margin: 0; font-size: 1.9rem; }}
.cg-cabecalho p  {{ margin: 2px 0 0; color: var(--cg-text-muted); }}

.cg-card {{
    background: var(--cg-bg-card);
    border: 1px solid var(--cg-border);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px 0;
}}
.cg-card-muted {{
    background: var(--cg-bg-elev);
    border: 1px dashed var(--cg-border-soft);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--cg-text-muted);
    font-size: 0.9rem;
}}

.cg-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    margin: 3px 4px 3px 0;
    border-radius: 999px;
    background: rgba(245, 158, 11, 0.10);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: var(--cg-accent-soft);
    font-size: 0.82rem;
    font-family: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
    font-weight: 500;
}}
.cg-badge-cyan {{
    background: rgba(6, 182, 212, 0.10);
    border-color: rgba(6, 182, 212, 0.35);
    color: #67E8F9;
}}
.cg-badge-muted {{
    background: rgba(139, 148, 158, 0.10);
    border-color: rgba(139, 148, 158, 0.30);
    color: var(--cg-text-muted);
}}

.cg-tool-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    margin: 4px 0;
    background: var(--cg-bg-elev);
    border: 1px solid var(--cg-border-soft);
}}
.cg-tool-row:hover {{ border-color: var(--cg-border); }}

.cg-chat-btn-label {{
    font-size: 0.85rem;
    color: var(--cg-text-muted);
}}
.cg-chat-btn-label strong {{
    color: var(--cg-text);
    font-weight: 500;
}}

.cg-aviso-truncado {{
    border-left: 3px solid var(--cg-warning);
    background: rgba(245, 158, 11, 0.08);
    padding: 8px 12px;
    border-radius: 6px;
    color: var(--cg-accent-soft);
    font-size: 0.9rem;
    margin-top: 8px;
}}
</style>
"""


def aplicar_estilo() -> None:
    """Injeta o CSS global da aplicação (chamar uma única vez no início)."""
    st.markdown(_CSS_GLOBAL, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers visuais
# ---------------------------------------------------------------------------
def emoji_tool(nome: str) -> str:
    return EMOJIS.get(nome, "🔧")


def badge(nome: str, variante: str = "default") -> str:
    """Retorna HTML de um badge/chip de ferramenta."""
    cls = {
        "default": "cg-badge",
        "cyan": "cg-badge-cyan",
        "muted": "cg-badge-muted",
    }.get(variante, "cg-badge")
    emoji = emoji_tool(nome)
    return f'<span class="{cls}">{emoji} <code style="background:transparent;border:none;color:inherit;padding:0">{nome}</code></span>'


def badges_html(nomes: Iterable[str], variante: str = "default") -> str:
    return "".join(badge(n, variante) for n in nomes)


# ---------------------------------------------------------------------------
# Componentes de layout
# ---------------------------------------------------------------------------
def renderizar_cabecalho() -> None:
    """Cabeçalho principal (coluna de chat)."""
    st.markdown(
        f"""
        <div class="cg-cabecalho">
            <h1>⚖️ Assistente CGU</h1>
            <p>Consultas especializadas sobre <strong>Processos de Apuração de Responsabilidades</strong>
            — PAD e PAR — com RAG sobre o corpus oficial.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def renderizar_sidebar_config(
    thread_id: str,
    ferramentas_nomes: list[str],
    on_nova_conversa,
    on_carregar_chat,
) -> None:
    """Sidebar de configurações, ferramentas e histórico de chats."""
    with st.sidebar:
        st.markdown("## ⚙️ Configurações")
        st.caption(f"Thread: `{thread_id[:8]}...`")

        if st.button("🗑️ Nova conversa", use_container_width=True, type="secondary"):
            on_nova_conversa()

        st.divider()

        # Ferramentas disponíveis
        with st.expander(f"🔧 Ferramentas disponíveis ({len(ferramentas_nomes)})", expanded=False):
            linhas = "".join(
                f'<div class="cg-tool-row">{badge(n, "cyan")}</div>'
                for n in ferramentas_nomes
            )
            st.markdown(linhas, unsafe_allow_html=True)

        st.divider()

        # Info do corpus/modelo
        st.markdown("### 📚 Corpus & Modelo")
        st.markdown(
            """
            <div class="cg-card-muted">
                <div><strong style="color:#E6EDF3">Corpus:</strong> 6 PDFs · 1567 trechos</div>
                <div style="margin-top:6px"><strong style="color:#E6EDF3">Modelo:</strong>
                <code style="color:#FCD34D;background:transparent;border:none;padding:0">gemma4:e4b</code>
                <span style="color:#8B949E;font-size:0.85rem">(Ollama local)</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # Chats anteriores
        st.markdown("### 💬 Chats anteriores")
        on_carregar_chat()  # callback que renderiza a lista (ver app.py)


def renderizar_detalhes_execucao(meta: dict) -> None:
    """Expander com ferramentas, skills e status de truncamento."""
    ferramentas_usadas = meta.get("ferramentas", [])
    skills_usadas = meta.get("skills", [])
    truncada = meta.get("truncada", False)

    if not (ferramentas_usadas or skills_usadas or truncada):
        return

    with st.expander("ℹ️ Detalhes da execução", expanded=False):
        if ferramentas_usadas:
            st.markdown("**Consultas realizadas:**")
            for c in ferramentas_usadas:
                nome_tool = c.get("nome", "ferramenta")
                args_tool = c.get("args", {})
                st.markdown(
                    f'<div class="cg-tool-row">{badge(nome_tool, "cyan")}</div>',
                    unsafe_allow_html=True,
                )
                if isinstance(args_tool, dict):
                    st.code(json.dumps(args_tool, ensure_ascii=False, indent=2), language="json")
                else:
                    st.code(str(args_tool), language="text")

        if skills_usadas:
            st.markdown(f"**Skills:** {badges_html(skills_usadas, 'muted')}", unsafe_allow_html=True)

        if truncada:
            st.markdown(
                '<div class="cg-aviso-truncado">⚠️ Resposta truncada.</div>',
                unsafe_allow_html=True,
            )


def renderizar_mensagem(msg: dict) -> None:
    """Renderiza uma mensagem do histórico (user ou assistant)."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["texto"])
        if msg["role"] == "assistant" and msg.get("meta"):
            renderizar_detalhes_execucao(msg["meta"])