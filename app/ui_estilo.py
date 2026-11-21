"""
Camada visual do Assistente.
Centraliza: tema CSS, componentes reutilizáveis (cabeçalho, sidebar,
badges de ferramentas, renderização de mensagens e detalhes de execução).
Não depende de classes internas instáveis do Streamlit.

Acessibilidade (painel "♿ Acessibilidade e aparência" na sidebar):
  - Tema: Automático (segue o sistema) / Claro / Escuro
  - Alto contraste (claro e escuro), bordas de 2px e texto preto/branco puro
  - Tamanho da letra de 80% a 150% (passos de 10%)
  - Estrelas ao fundo (discretas, cintilação suave; desligáveis; sem estrelas no alto contraste)
  - Reduzir animações (também respeita prefers-reduced-motion do sistema; as estrelas ficam fixas)
  - Foco de teclado sempre visível, alvos de toque >= 44px, suporte a forced-colors

As preferências ficam em st.session_state e o CSS é regenerado a cada execução,
então nenhum JavaScript é necessário (st.markdown NÃO executa <script>). Todas as paletas foram checadas contra
WCAG 2.1 AA (texto >= 4,5:1; bordas de componentes >= 3:1).

Dica: em .streamlit/config.toml defina  [theme] primaryColor = "#6B97FF"
para que radio/checkbox nativos usem a cor de destaque da aplicação.
"""
from __future__ import annotations

import json
import random
from typing import Iterable

from cgu_rag.config import settings

import streamlit as st

# ---------------------------------------------------------------------------
# Paletas e tokens de design
# ---------------------------------------------------------------------------
# Paleta escura (azulada, inspirada na apresentação SYSOP-AI). Mantida com as
# mesmas chaves de antes por compatibilidade com módulos que importem TEMA
# (ex.: ui_grafo).
TEMA = {
    "bg": "#0E1526",
    "bg_elev": "#121C33",
    "bg_card": "#18233D",
    "border": "#2B3A5C",
    "border_soft": "#223050",
    "text": "#E9EEFB",
    "text_muted": "#A9B6D0",
    "text_dim": "#93A2C2",
    "accent": "#6B97FF",       # azul — destaque primário
    "accent_soft": "#9DBBFF",
    "accent_cyan": "#4CC3DC",  # destaque secundário
    "success": "#3FD29B",
    "warning": "#F0A04B",
    "danger": "#FF7F9B",
    "user_bubble": "#1D2E57",
    "assistant_bubble": "#18233D",
}

# Tokens extras usados pelo CSS. "scheme" vira a propriedade color-scheme;
# as demais chaves viram variáveis --cg-<chave-com-hifens>.
_ESCURO = {
    "scheme": "dark",
    "bg": "#0E1526", "bg_elev": "#121C33", "bg_card": "#18233D",
    "border": "#2B3A5C", "border_soft": "#223050", "border_strong": "#6C7FA6",
    "text": "#E9EEFB", "text_muted": "#A9B6D0", "text_dim": "#93A2C2",
    "accent": "#6B97FF", "accent_soft": "#9DBBFF", "accent_fg": "#9DBBFF",
    "accent_cyan": "#4CC3DC", "cyan_fg": "#7FD8EC",
    "success": "#3FD29B", "warning": "#F0A04B", "danger": "#FF7F9B",
    "warn_fg": "#F0A04B", "warn_tint": "rgba(240,160,75,0.12)",
    "link": "#8FB4FF", "on_accent": "#0E1526",
    "btn_from": "#6B97FF", "btn_to": "#4F7DF0", "focus": "#FFD166",
    "code_fg": "#BFD3FF",
    "user_from": "#1D2E57", "user_to": "#16254A", "user_border": "#3E5DA0",
    "header_bg": "rgba(14, 21, 38, 0.85)", "glow": "#17254A",
    "accent_tint": "rgba(107,151,255,0.12)", "accent_line": "rgba(107,151,255,0.50)",
    "cyan_tint": "rgba(76,195,220,0.12)", "cyan_line": "rgba(76,195,220,0.45)",
    "muted_tint": "rgba(169,182,208,0.12)", "muted_line": "rgba(169,182,208,0.40)",
    "shadow": "0 6px 20px rgba(0,0,0,0.35)",
    "star": "rgba(223,233,255,0.95)", "star_dim": "rgba(169,190,235,0.55)",
    "border_w": "1px",
}

_CLARO = {
    "scheme": "light",
    "bg": "#F3F6FC", "bg_elev": "#E9EFFA", "bg_card": "#FFFFFF",
    "border": "#C9D5EA", "border_soft": "#DCE4F2", "border_strong": "#6A7A99",
    "text": "#14213D", "text_muted": "#55657F", "text_dim": "#52617C",
    "accent": "#2563EB", "accent_soft": "#1D4ED8", "accent_fg": "#1D4ED8",
    "accent_cyan": "#0B7C94", "cyan_fg": "#0A6A7F",
    "success": "#047857", "warning": "#C25E00", "danger": "#BE123C",
    "warn_fg": "#9A4A00", "warn_tint": "rgba(194,94,0,0.10)",
    "link": "#1D4ED8", "on_accent": "#FFFFFF",
    "btn_from": "#2563EB", "btn_to": "#1D4ED8", "focus": "#14213D",
    "code_fg": "#1E3A8A",
    "user_from": "#E6EEFD", "user_to": "#D9E6FC", "user_border": "#8FB0F0",
    "header_bg": "rgba(243, 246, 252, 0.92)", "glow": "#E1EAFB",
    "accent_tint": "rgba(37,99,235,0.08)", "accent_line": "rgba(37,99,235,0.45)",
    "cyan_tint": "rgba(11,124,148,0.10)", "cyan_line": "rgba(11,124,148,0.50)",
    "muted_tint": "rgba(85,101,127,0.08)", "muted_line": "rgba(85,101,127,0.40)",
    "shadow": "0 6px 20px rgba(30,58,138,0.12)",
    "star": "rgba(37,99,235,0.55)", "star_dim": "rgba(37,99,235,0.28)",
    "border_w": "1px",
}

_CLARO_AC = {
    "scheme": "light",
    "bg": "#FFFFFF", "bg_elev": "#FFFFFF", "bg_card": "#FFFFFF",
    "border": "#000000", "border_soft": "#000000", "border_strong": "#000000",
    "text": "#000000", "text_muted": "#1A1A1A", "text_dim": "#1A1A1A",
    "accent": "#0036B3", "accent_soft": "#0036B3", "accent_fg": "#0036B3",
    "accent_cyan": "#005A6E", "cyan_fg": "#004A5C",
    "success": "#005C3F", "warning": "#8A3F00", "danger": "#8F0030",
    "warn_fg": "#8A3F00", "warn_tint": "#FFF0D6",
    "link": "#0036B3", "on_accent": "#FFFFFF",
    "btn_from": "#0036B3", "btn_to": "#0036B3", "focus": "#000000",
    "code_fg": "#000000",
    "user_from": "#EAF0FF", "user_to": "#EAF0FF", "user_border": "#000000",
    "header_bg": "#FFFFFF", "glow": "#FFFFFF",
    "accent_tint": "#EAF0FF", "accent_line": "#000000",
    "cyan_tint": "#E1F6FB", "cyan_line": "#000000",
    "muted_tint": "#F0F0F0", "muted_line": "#000000",
    "shadow": "none",
    "star": "rgba(0,0,0,0)", "star_dim": "rgba(0,0,0,0)",
    "border_w": "2px",
}

_ESCURO_AC = {
    "scheme": "dark",
    "bg": "#000000", "bg_elev": "#000000", "bg_card": "#000000",
    "border": "#FFFFFF", "border_soft": "#FFFFFF", "border_strong": "#FFFFFF",
    "text": "#FFFFFF", "text_muted": "#F2F2F2", "text_dim": "#E0E0E0",
    "accent": "#9DBBFF", "accent_soft": "#9DBBFF", "accent_fg": "#9DBBFF",
    "accent_cyan": "#6FDCF2", "cyan_fg": "#6FDCF2",
    "success": "#5DF0B6", "warning": "#FFB766", "danger": "#FF9DB5",
    "warn_fg": "#FFB766", "warn_tint": "#2E1D08",
    "link": "#9DBBFF", "on_accent": "#000000",
    "btn_from": "#9DBBFF", "btn_to": "#9DBBFF", "focus": "#FFD166",
    "code_fg": "#BFD3FF",
    "user_from": "#0D1A3A", "user_to": "#0D1A3A", "user_border": "#FFFFFF",
    "header_bg": "#000000", "glow": "#000000",
    "accent_tint": "#0D1A3A", "accent_line": "#FFFFFF",
    "cyan_tint": "#08272F", "cyan_line": "#FFFFFF",
    "muted_tint": "#1A1A1A", "muted_line": "#FFFFFF",
    "shadow": "none",
    "star": "rgba(0,0,0,0)", "star_dim": "rgba(0,0,0,0)",
    "border_w": "2px",
}

PALETAS = {
    ("escuro", False): _ESCURO,
    ("claro", False): _CLARO,
    ("escuro", True): _ESCURO_AC,
    ("claro", True): _CLARO_AC,
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
TIPO_TOOL = {
    "consultar_base": "Base local (RAG)",
    "buscar_web": "Web (DuckDuckGo)",
    "buscar_url": "Web (leitura de URL)",
    "resumir_trecho": "Skill",
    "transparencia_sancoes": "Transparência (REST)",
    "transparencia_pep": "Transparência (REST)",
    "transparencia_despesas_favorecido": "Transparência (REST)",
    "transparencia_despesas_documentos": "Transparência (REST)",
    "cnpj_consultar": "CNPJ (REST)",
    "cnpj_processos": "CNPJ (REST)",
}

# ---------------------------------------------------------------------------
# Preferências de acessibilidade (session_state)
# ---------------------------------------------------------------------------
OPCOES_TEMA = ["Automático", "Claro", "Escuro"]
FS_MIN, FS_MAX, FS_PASSO, FS_PADRAO = 80, 150, 10, 105

_K_TEMA = "a11y_tema"
_K_FS = "a11y_fs"
_K_CONTRASTE = "a11y_contraste"
_K_MOVIMENTO = "a11y_movimento"
_K_ESTRELAS = "a11y_estrelas"


def _iniciar_prefs() -> None:
    st.session_state.setdefault(_K_TEMA, "Automático")
    st.session_state.setdefault(_K_FS, FS_PADRAO)
    st.session_state.setdefault(_K_CONTRASTE, False)
    st.session_state.setdefault(_K_MOVIMENTO, False)
    st.session_state.setdefault(_K_ESTRELAS, True)


def _ajustar_fonte(delta: int) -> None:
    atual = int(st.session_state.get(_K_FS, FS_PADRAO))
    st.session_state[_K_FS] = max(FS_MIN, min(FS_MAX, atual + delta))


def _restaurar_prefs() -> None:
    st.session_state[_K_TEMA] = "Automático"
    st.session_state[_K_FS] = FS_PADRAO
    st.session_state[_K_CONTRASTE] = False
    st.session_state[_K_MOVIMENTO] = False
    st.session_state[_K_ESTRELAS] = True


# ---------------------------------------------------------------------------
# Geração do CSS
# ---------------------------------------------------------------------------
def _bloco_variaveis(paleta: dict) -> str:
    """Converte uma paleta em declarações CSS (color-scheme + --cg-*)."""
    partes = []
    for chave, valor in paleta.items():
        if chave == "scheme":
            partes.append(f"color-scheme:{valor}")
        else:
            partes.append(f"--cg-{chave.replace('_', '-')}:{valor}")
    return ";".join(partes)


def _css_variaveis(tema: str, alto_contraste: bool) -> str:
    """Variáveis do tema escolhido. 'Automático' segue prefers-color-scheme."""
    claro = _bloco_variaveis(PALETAS[("claro", alto_contraste)])
    escuro = _bloco_variaveis(PALETAS[("escuro", alto_contraste)])
    if tema == "Claro":
        return f":root{{{claro}}}"
    if tema == "Escuro":
        return f":root{{{escuro}}}"
    return (
        f":root{{{claro}}}"
        f"@media (prefers-color-scheme: dark){{:root{{{escuro}}}}}"
    )


_CSS_ESTATICO = """
/* ---------- Base ---------- */
html, body, [class*="css"] {
    color: var(--cg-text);
    font-family: "Atkinson Hyperlegible", "Inter", sans-serif;
    -webkit-text-size-adjust: 100%;
}
.stApp {
    color: var(--cg-text);
    background: radial-gradient(1200px 600px at 10% -10%, var(--cg-glow) 0%, var(--cg-bg) 55%) fixed;
}
/* Contêineres transparentes: deixam o fundo (e as estrelas) aparecerem */
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background: transparent !important;
}
[data-testid="stBottom"], [data-testid="stBottom"] > div {
    background: var(--cg-bg) !important;   /* área do campo de chat, nos dois temas */
}
header[data-testid="stHeader"] {
    background: var(--cg-header-bg);
    backdrop-filter: blur(8px);
    border-bottom: var(--cg-border-w) solid var(--cg-border-soft);
}
header[data-testid="stHeader"] :is(button, a, span, svg) {
    color: var(--cg-text) !important;
}

/* ---------- Foco de teclado sempre visível ---------- */
:focus-visible,
button:focus-visible,
[role="button"]:focus-visible,
[data-baseweb] :focus-visible,
summary:focus-visible,
a:focus-visible {
    outline: 3px solid var(--cg-focus) !important;
    outline-offset: 2px !important;
    border-radius: 6px;
}

/* ---------- Tipografia (rem: acompanha a escala de fonte) ---------- */
h1, h2, h3, h4 {
    color: var(--cg-text);
    letter-spacing: -0.01em;
}
h1 {
    background: linear-gradient(90deg, var(--cg-accent-fg), var(--cg-cyan-fg));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 700;
}
[data-testid="stMarkdownContainer"] :is(p, li, td, th) {
    color: var(--cg-text) !important;
    font-size: 1.1rem;
    line-height: 1.75;
}
[data-testid="stMarkdownContainer"] a,
a { color: var(--cg-link) !important; text-decoration: underline; text-underline-offset: 2px; }
[data-testid="stWidgetLabel"] :is(p, span, label),
label { color: var(--cg-text) !important; font-size: 1rem; }
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] :is(p, span) {
    color: var(--cg-text-muted) !important;
    font-size: 0.875rem;
}
code, pre {
    background: var(--cg-bg-elev) !important;
    color: var(--cg-code-fg) !important;
    border: var(--cg-border-w) solid var(--cg-border-soft);
    border-radius: 6px;
    font-size: 0.9rem;
}
pre *, [data-testid="stCode"] * {
    color: var(--cg-code-fg) !important;   /* garante legibilidade em qualquer tema */
    background: transparent !important;
}

/* ---------- Chat bubbles ---------- */
.stChatMessage {
    background: transparent !important;
}
div[data-testid="stChatMessage"] {
    background: var(--cg-bg-card);
    border: var(--cg-border-w) solid var(--cg-border);
    border-radius: 14px;
    padding: 14px 16px;
    box-shadow: var(--cg-shadow);
}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    border-color: var(--cg-user-border);
    background: linear-gradient(180deg, var(--cg-user-from) 0%, var(--cg-user-to) 100%);
}

/* ---------- Inputs ---------- */
.stTextInput input,
.stChatInput textarea,
.stChatInputContainer,
[data-testid="stChatInput"],
[data-testid="stChatInput"] textarea,
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] input:focus,
[data-baseweb="input"],
[data-baseweb="textarea"],
[data-baseweb="select"] > div,
[data-testid="stChatInput"] [data-baseweb="input"],
[data-testid="stChatInput"] [data-baseweb="textarea"] {
    background: var(--cg-bg-elev) !important;
    border: var(--cg-border-w) solid var(--cg-border-strong) !important;
    color: var(--cg-text) !important;
    border-radius: 12px !important;
    font-size: 1rem !important;
    box-shadow: none !important;
}
/* Camadas internas do chat_input (BaseWeb) herdam o fundo nativo do tema do sistema */
[data-testid="stBottomBlockContainer"] { background-color: var(--cg-bg) !important; }
[data-testid="stChatInput"] :is(div, textarea) {
    background-color: var(--cg-bg-elev) !important;
    color: var(--cg-text) !important;
}
[data-testid="stChatInput"] textarea::placeholder,
.stTextInput input::placeholder,
[data-testid="stTextInput"] input::placeholder {
    color: var(--cg-text-muted) !important;
    opacity: 1 !important;
}
.stTextInput input:focus,
.stChatInput textarea:focus,
[data-testid="stChatInput"]:focus-within,
[data-testid="stTextInput"]:focus-within {
    border-color: var(--cg-accent) !important;
    box-shadow: 0 0 0 2px var(--cg-accent-tint) !important;
}

/* ---------- Botões ----------
   Seletores baseados em data-testid e em descendente (não ">"), porque o
   Streamlit envolve o <button> em wrappers extras (tooltip do help=, colunas,
   versões novas do DOM). Com "> button" a regra não casava: o fundo ficava
   no valor nativo (tema do sistema) enquanto o texto, que é coberto pela
   regra do stMarkdownContainer, ia para a cor do nosso tema. */
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]) {
    background: var(--cg-bg-card) !important;
    background-color: var(--cg-bg-card) !important;
    color: var(--cg-text) !important;
    border: var(--cg-border-w) solid var(--cg-border-strong) !important;
    border-radius: 10px !important;
    transition: all 0.18s ease !important;
    font-weight: 500 !important;
    font-size: 1rem !important;
    min-height: 2.75rem !important;
    box-shadow: none !important;
}
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]) :is(p, span, div, svg, path) {
    color: inherit !important;
    fill: currentColor;
    font-size: inherit !important;
    background: transparent !important;
}
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):hover {
    background: var(--cg-bg-elev) !important;
    background-color: var(--cg-bg-elev) !important;
    border-color: var(--cg-accent) !important;
    color: var(--cg-accent-fg) !important;
    transform: translateY(-1px) !important;
}
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):disabled {
    opacity: 0.55 !important;
    cursor: not-allowed !important;
    color: var(--cg-text-muted) !important;
    transform: none !important;
}
html body :is(button[data-testid="stBaseButton-primary"], .stButton button[kind="primary"]) {
    background: linear-gradient(135deg, var(--cg-btn-from), var(--cg-btn-to)) !important;
    color: var(--cg-on-accent) !important;
    border: none !important;
    font-weight: 600 !important;
}
html body :is(button[data-testid="stBaseButton-primary"], .stButton button[kind="primary"]):hover { color: var(--cg-on-accent) !important; }

/* Botão de enviar do chat_input */
[data-testid="stChatInputSubmitButton"] {
    background: transparent !important;
    color: var(--cg-accent-fg) !important;
}
[data-testid="stChatInputSubmitButton"] svg { fill: currentColor !important; color: inherit !important; }
[data-testid="stChatInputSubmitButton"]:disabled { color: var(--cg-text-muted) !important; }

/* ---------- Expander (detalhes) ---------- */
.streamlit-expanderHeader,
[data-testid="stExpander"] details > summary {
    background: var(--cg-bg-elev);
    border: var(--cg-border-w) solid var(--cg-border-soft);
    border-radius: 10px;
    color: var(--cg-text-muted);
    font-size: 0.95rem;
}
[data-testid="stExpander"] details > summary :is(p, span, svg) {
    color: var(--cg-text-muted) !important;
}
.streamlit-expanderHeader:hover,
[data-testid="stExpander"] details > summary:hover {
    color: var(--cg-accent-fg);
    border-color: var(--cg-border-strong);
}
[data-testid="stExpander"] details {
    border: var(--cg-border-w) solid var(--cg-border-soft);
    border-radius: 10px;
    background: var(--cg-bg-elev);
}
.streamlit-expanderContent {
    background: var(--cg-bg-elev);
    border: var(--cg-border-w) solid var(--cg-border-soft);
    border-top: none;
    border-radius: 0 0 10px 10px;
    padding: 12px 14px;
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--cg-bg-elev) 0%, var(--cg-bg) 100%);
    border-right: var(--cg-border-w) solid var(--cg-border-soft);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: var(--cg-text);
}

/* ---------- Dividers ---------- */
hr {
    border-color: var(--cg-border) !important;
    margin: 14px 0;
}

/* ---------- Scrollbars ---------- */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--cg-bg); }
::-webkit-scrollbar-thumb {
    background: var(--cg-border-strong);
    border-radius: 5px;
}
::-webkit-scrollbar-thumb:hover { background: var(--cg-text-dim); }

/* ---------- Componentes customizados (badges, cards) ---------- */
.cg-cabecalho {
    padding: 10px 14px;
    border-left: 4px solid var(--cg-accent);
    background: linear-gradient(90deg, var(--cg-accent-tint), transparent);
    border-radius: 0 10px 10px 0;
    margin-bottom: 18px;
}
.cg-cabecalho h1 { margin: 0; font-size: 1.9rem; }
[data-testid="stMarkdownContainer"] .cg-cabecalho p { margin: 2px 0 0; color: var(--cg-text-muted) !important; }
.cg-cabecalho strong { color: var(--cg-text); }

.cg-card {
    background: var(--cg-bg-card);
    border: var(--cg-border-w) solid var(--cg-border);
    border-radius: 12px;
    padding: 14px 16px;
    margin: 8px 0;
    box-shadow: var(--cg-shadow);
}
.cg-card-muted {
    background: var(--cg-bg-elev);
    border: var(--cg-border-w) dashed var(--cg-border-strong);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--cg-text-muted);
    font-size: 0.9rem;
}
.cg-card-muted strong { color: var(--cg-text); }
.cg-card-muted code {
    color: var(--cg-accent-fg) !important;
    background: transparent !important;
    border: none !important;
    padding: 0;
}
.cg-fonte-pct {
    text-align: center;
    font-weight: 700;
    font-size: 1rem;
    padding-top: 0.55rem;
    color: var(--cg-text);
}

.cg-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    margin: 3px 4px 3px 0;
    border-radius: 999px;
    background: var(--cg-accent-tint);
    border: var(--cg-border-w) solid var(--cg-accent-line);
    color: var(--cg-accent-fg);
    font-size: 0.85rem;
    font-family: "JetBrains Mono", "Fira Code", ui-monospace, monospace;
    font-weight: 500;
}
.cg-badge-cyan {
    background: var(--cg-cyan-tint);
    border-color: var(--cg-cyan-line);
    color: var(--cg-cyan-fg);
}
.cg-badge-muted {
    background: var(--cg-muted-tint);
    border-color: var(--cg-muted-line);
    color: var(--cg-text-muted);
}
[data-testid="stMarkdownContainer"] .cg-badge { color: var(--cg-accent-fg) !important; }
[data-testid="stMarkdownContainer"] .cg-badge-cyan { color: var(--cg-cyan-fg) !important; }
[data-testid="stMarkdownContainer"] .cg-badge-muted { color: var(--cg-text-muted) !important; }
.cg-badge code { background: transparent !important; border: none !important; color: inherit !important; padding: 0; }

/* Remove o fundo e a borda de qualquer elemento dentro da linha */
.cg-tool-row * {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    
    /* Opcional: Para tirar o aspecto de "código" e deixar a fonte normal */
    font-family: inherit !important; 
    font-weight: normal !important;
    text-decoration: none !important;
}
.cg-tool-row:hover { border-color: var(--cg-border-strong); }

.cg-chat-btn-label {
    font-size: 0.9rem;
    color: var(--cg-text-muted);
}
.cg-chat-btn-label strong {
    color: var(--cg-text);
    font-weight: 500;
}

.cg-aviso-truncado {
    border-left: 4px solid var(--cg-warning);
    background: var(--cg-warn-tint);
    padding: 8px 12px;
    border-radius: 6px;
    color: var(--cg-warn-fg);
    font-size: 0.95rem;
    margin-top: 8px;
}
[data-testid="stMarkdownContainer"] .cg-aviso-truncado { color: var(--cg-warn-fg) !important; }

/* ---------- Widgets nativos do Streamlit/BaseWeb seguindo o tema ---------- */
/* menus suspensos, tooltips e popovers (renderizados fora da árvore principal) */
[data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="tooltip"] > div,
[data-baseweb="tooltip"] [role="tooltip"] {
    background: var(--cg-bg-card) !important;
    color: var(--cg-text) !important;
    border: var(--cg-border-w) solid var(--cg-border-strong);
    border-radius: 10px;
    box-shadow: var(--cg-shadow);
}
[data-baseweb="popover"] :is(li, span, p, div), [data-baseweb="tooltip"] :is(span, p, div) {
    color: var(--cg-text) !important;
}
[data-baseweb="menu"] li:hover, [data-baseweb="menu"] [aria-selected="true"] {
    background: var(--cg-accent-tint) !important;
}
/* caixa do checkbox e bolinha do radio não marcados */
[data-baseweb="checkbox"] > span:first-child, [data-baseweb="radio"] > div:first-child {
    border-color: var(--cg-border-strong) !important;
}
/* alertas, avisos e spinner */
[data-testid="stAlert"] {
    background: var(--cg-bg-elev) !important;
    border: var(--cg-border-w) solid var(--cg-border-strong);
    border-radius: 10px;
}
[data-testid="stAlert"] :is(p, span, div, svg) { color: var(--cg-text) !important; }
[data-testid="stSpinner"] :is(p, span, div) { color: var(--cg-text-muted) !important; }
[data-testid="stToast"], [data-testid="stToast"] * {
    background: var(--cg-bg-card) !important;
    color: var(--cg-text) !important;
}
/* texto "disabled" continua legível */
:is(button, input, textarea):disabled { color: var(--cg-text-muted) !important; }
/* sidebar levemente translúcida: deixa as estrelas aparecerem nela também */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,
        color-mix(in srgb, var(--cg-bg-elev) 82%, transparent) 0%,
        color-mix(in srgb, var(--cg-bg) 82%, transparent) 100%);
    backdrop-filter: blur(2px);
}
section[data-testid="stSidebar"] > div { background: transparent !important; }

/* ---------- Alto contraste / modo forçado do sistema ---------- */
@media (forced-colors: active) {
    h1 { background: none; color: CanvasText; -webkit-text-fill-color: CanvasText; }
    .cg-badge, .cg-tool-row, .cg-card, .cg-card-muted,
    div[data-testid="stChatMessage"], :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]) { border: 2px solid CanvasText; }
    :focus-visible { outline: 4px solid Highlight !important; }
}

"""

# No alto contraste o texto em degradê é trocado por cor sólida (legibilidade).
_CSS_ALTO_CONTRASTE = """
h1 { background: none !important; -webkit-text-fill-color: var(--cg-text); color: var(--cg-text) !important; }
:focus-visible, button:focus-visible, [data-baseweb] :focus-visible { outline-width: 4px !important; }
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):hover { background: var(--cg-text) !important; color: var(--cg-bg) !important; }
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):hover :is(p, span, div) { color: var(--cg-bg) !important; }
a { font-weight: 700; }
"""

_CSS_SEM_MOVIMENTO = """
*, *::before, *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
}
html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):hover { transform: none !important; }
"""

_CSS_PREFERE_MENOS_MOVIMENTO = """
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        scroll-behavior: auto !important;
    }
    html body :is(.stButton button, [data-testid="stFormSubmitButton"] button, button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-secondaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"]):hover { transform: none !important; }
}

"""


# ---------------------------------------------------------------------------
# Estrelas ao fundo (CSS puro, discretas, com cintilação suave)
# ---------------------------------------------------------------------------
def _gradientes_estrelas(qtd: int, r_min: float, r_max: float, semente: int, cor: str) -> str:
    """Gera 'qtd' pontos de luz posicionados de forma pseudoaleatória (determinística)."""
    rng = random.Random(semente)
    itens = []
    for _ in range(qtd):
        x, y = rng.uniform(1, 99), rng.uniform(1, 99)
        r = rng.uniform(r_min, r_max)
        itens.append(
            f"radial-gradient({r:.2f}px {r:.2f}px at {x:.1f}% {y:.1f}%,{cor} 35%,transparent 100%)"
        )
    return ",".join(itens)


def _css_estrelas() -> str:
    """Três camadas: uma estática (bem tênue) e duas que cintilam em ritmos diferentes."""
    estaticas = _gradientes_estrelas(55, 0.9, 1.5, 11, "var(--cg-star-dim)")
    camada_a = _gradientes_estrelas(26, 1.0, 1.7, 23, "var(--cg-star)")
    camada_b = _gradientes_estrelas(20, 1.1, 2.0, 37, "var(--cg-star)")
    return (
        ".stApp{isolation:isolate;"
        "background-image:" + estaticas + ",radial-gradient(1200px 600px at 10% -10%,var(--cg-glow) 0%,var(--cg-bg) 55%);"
        "background-attachment:fixed;background-repeat:no-repeat;background-size:100% 100%;"
        "background-color:var(--cg-bg);}"
        ".stApp::before,.stApp::after{content:\"\";position:fixed;inset:0;z-index:-1;"
        "pointer-events:none;background-repeat:no-repeat;background-size:100% 100%;opacity:.9;}"
        ".stApp::before{background-image:" + camada_a + ";animation:cg-cintilar 6s ease-in-out infinite;}"
        ".stApp::after{background-image:" + camada_b + ";animation:cg-cintilar 9s ease-in-out -3.5s infinite;}"
        "@keyframes cg-cintilar{0%,100%{opacity:.35;}50%{opacity:1;}}"
    )


def _montar_css() -> str:
    tema = st.session_state.get(_K_TEMA, "Automático")
    if tema not in OPCOES_TEMA:
        tema = "Automático"
    alto = bool(st.session_state.get(_K_CONTRASTE, False))
    fs = int(st.session_state.get(_K_FS, FS_PADRAO))
    fs = max(FS_MIN, min(FS_MAX, fs))
    sem_mov = bool(st.session_state.get(_K_MOVIMENTO, False))
    estrelas = bool(st.session_state.get(_K_ESTRELAS, True))

    css = "<style>"
    css += _css_variaveis(tema, alto)
    css += f"html{{font-size:{fs}%;}}"
    css += _CSS_ESTATICO
    if estrelas and not alto:      # alto contraste: fundo liso, sem estrelas
        css += _css_estrelas()
    if alto:
        css += _CSS_ALTO_CONTRASTE
    css += _CSS_PREFERE_MENOS_MOVIMENTO
    if sem_mov:
        css += _CSS_SEM_MOVIMENTO
    css += "</style>"
    return css


def css_tema_atual() -> str:
    """
    CSS (sem tags <style>) com as variáveis --cg-* do tema escolhido e o tamanho
    de letra atual. Serve para componentes que renderizam dentro de iframe
    (st.components.v1.html), que não herdam o CSS da página, como o mapa de
    conhecimento em ui_grafo.py.
    """
    _iniciar_prefs()
    tema = st.session_state.get(_K_TEMA, "Automático")
    if tema not in OPCOES_TEMA:
        tema = "Automático"
    alto = bool(st.session_state.get(_K_CONTRASTE, False))
    fs = max(FS_MIN, min(FS_MAX, int(st.session_state.get(_K_FS, FS_PADRAO))))
    return _css_variaveis(tema, alto) + f"html{{font-size:{fs}%;}}"


def movimento_reduzido() -> bool:
    """True se o usuário pediu para reduzir animações no painel de acessibilidade."""
    _iniciar_prefs()
    return bool(st.session_state.get(_K_MOVIMENTO, False))


def fator_fonte() -> float:
    """Escala de fonte atual (1.0 = 100%)."""
    _iniciar_prefs()
    return max(FS_MIN, min(FS_MAX, int(st.session_state.get(_K_FS, FS_PADRAO)))) / 100


def aplicar_estilo() -> None:
    """Injeta o CSS global da aplicação (chamar uma única vez no início de cada execução)."""
    _iniciar_prefs()
    st.markdown(_montar_css(), unsafe_allow_html=True)


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
    return (
        f'<span class="{cls}"><span aria-hidden="true">{emoji}</span> '
        f'<code style="background:transparent;border:none;color:inherit;padding:0">{nome}</code></span>'
    )


def badges_html(nomes: Iterable[str], variante: str = "default") -> str:
    return "".join(badge(n, variante) for n in nomes)


# ---------------------------------------------------------------------------
# Painel de acessibilidade
# ---------------------------------------------------------------------------
def renderizar_controles_acessibilidade() -> None:
    """Controles de tema, contraste, tamanho de letra e movimento."""
    _iniciar_prefs()
    fs = int(st.session_state[_K_FS])

    with st.expander("♿ Acessibilidade e aparência", expanded=False):
        st.markdown("**Tamanho da letra**")
        c_menos, c_pct, c_mais = st.columns([1, 1.1, 1])
        with c_menos:
            st.button(
                "A−",
                key="a11y_fonte_menos",
                on_click=_ajustar_fonte,
                args=(-FS_PASSO,),
                disabled=fs <= FS_MIN,
                help="Diminuir tamanho da letra",
                use_container_width=True,
            )
        with c_pct:
            st.markdown(
                f'<div class="cg-fonte-pct" role="status" aria-live="polite" '
                f'aria-label="Tamanho da letra: {fs} por cento">{fs}%</div>',
                unsafe_allow_html=True,
            )
        with c_mais:
            st.button(
                "A+",
                key="a11y_fonte_mais",
                on_click=_ajustar_fonte,
                args=(FS_PASSO,),
                disabled=fs >= FS_MAX,
                help="Aumentar tamanho da letra",
                use_container_width=True,
            )

        st.radio(
            "Tema",
            OPCOES_TEMA,
            key=_K_TEMA,
            horizontal=True,
            help="Automático segue o tema claro/escuro do seu sistema.",
        )
        st.checkbox(
            "Alto contraste",
            key=_K_CONTRASTE,
            help="Texto preto/branco puro, bordas reforçadas e foco ampliado.",
        )
        st.checkbox(
            "Estrelas ao fundo",
            key=_K_ESTRELAS,
            help="Fundo estrelado discreto. É desativado automaticamente no alto contraste.",
        )
        st.checkbox(
            "Reduzir animações",
            key=_K_MOVIMENTO,
            help="Remove transições e animações da interface.",
        )
        st.button(
            "Restaurar padrão",
            key="a11y_restaurar",
            on_click=_restaurar_prefs,
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Componentes de layout
# ---------------------------------------------------------------------------
def renderizar_cabecalho() -> None:
    """Cabeçalho principal (coluna de chat)."""
    st.markdown(
        f"""
        <div class="cg-cabecalho">
            <h1><span aria-hidden="true">⚖️</span> Assistente Legislação Offline</h1>
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

        # Acessibilidade: tema, contraste, tamanho da letra
        renderizar_controles_acessibilidade()

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
            f"""
            <div class="cg-card-muted">
                <div><strong>Corpus:</strong> 6 PDFs · 1567 trechos</div>
                <div style="margin-top:6px"><strong>Modelo:</strong>
                <code>{settings.llm_model}</code>
                <span style="font-size:0.85rem">(Ollama local)</span></div>
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
    todas = meta.get("ferramentas", [])
    ferramentas_usadas = [c for c in todas if c.get("nome") != "resumir_trecho"]
    skills_usadas = meta.get("skills", [])
    truncada = meta.get("truncada", False)

    if not (ferramentas_usadas or skills_usadas or truncada):
        return

    with st.expander("ℹ️ Detalhes da execução", expanded=False):
        if ferramentas_usadas:
            st.markdown(f"**Ferramentas utilizadas ({len(ferramentas_usadas)}):**")
            for c in ferramentas_usadas:
                nome_tool = c.get("nome", "ferramenta")
                tipo = TIPO_TOOL.get(nome_tool, "Outra")
                args_tool = c.get("args", {})
                icone = "✅" if c.get("status", "success") == "success" else "❌"
                st.markdown(
                    f'<div class="cg-tool-row"><span aria-hidden="true">{icone}</span> '
                    f'{badge(nome_tool, "cyan")} <small>{tipo}</small></div>',
                    unsafe_allow_html=True,
                )
                st.code(json.dumps(args_tool, ensure_ascii=False, indent=2)
                        if isinstance(args_tool, dict) else str(args_tool), language="json")

        if skills_usadas:
            st.markdown(f"**Skills:** {badges_html(skills_usadas, 'muted')}", unsafe_allow_html=True)

        if truncada:
            st.markdown(
                '<div class="cg-aviso-truncado" role="alert"><span aria-hidden="true">⚠️</span> Resposta truncada.</div>',
                unsafe_allow_html=True,
            )


def renderizar_mensagem(msg: dict) -> None:
    """Renderiza uma mensagem do histórico (user ou assistant)."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["texto"])
        if msg["role"] == "assistant" and msg.get("meta"):
            renderizar_trace(msg["meta"])
            renderizar_detalhes_execucao(msg["meta"])
            
def renderizar_trace(estado: dict) -> None:
    """Renderiza um trace simplificado e visual do fluxo de execução do agente."""
    ferramentas = estado.get("ferramentas", [])
    skills = estado.get("skills", [])
    bloqueado = estado.get("bloqueado", "")

    with st.expander("🔍 Ver passo a passo do raciocínio (Trace)", expanded=False):
        st.markdown("📝 **Fluxo de Execução:**")
        
        if bloqueado:
            st.error(f"🛑 **Bloqueio de Segurança:** {bloqueado}")
            return

        st.markdown("1️⃣ **Entrada:** Pergunta do usuário recebida e validada.")

        if not ferramentas and not skills:
            st.markdown("2️⃣ **Decisão do Modelo:** Responder diretamente com conhecimento interno (sem consultar ferramentas).")
        else:
            st.markdown("2️⃣ **Decisão do Modelo:** Acionar ferramentas e/ou skills.")
            for f in ferramentas:
                icone = "✅" if f.get("status", "success") == "success" else "❌"
                args_str = ", ".join(f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}"
                                     for k, v in f.get("args", {}).items())
                st.markdown(f"   - {icone} 🛠️ **Ferramenta:** `{f['nome']}` ({args_str})")
            for s in skills:
                st.markdown(f"   - ⚡ **Skill:** `{s}`")

        if ferramentas:
            ok = sum(f.get("status", "success") == "success" for f in ferramentas)
            falhas = len(ferramentas) - ok
            st.markdown(f"3️⃣ **Execução:** {ok}/{len(ferramentas)} chamadas concluídas"
                        + (f" ({falhas} com erro)." if falhas else "."))
        st.markdown("4️⃣ **Síntese:** Modelo processou os resultados e gerou a resposta final (com fontes anexadas pelo sistema).")