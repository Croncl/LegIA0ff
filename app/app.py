"""
UI Streamlit (R12) — Assistente CGU RAG (PAD e PAR).

Uso (na raiz do projeto):
  streamlit run app/app.py
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta
from cgu_rag.agente.grafo import conversar, criar_grafo
from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web
from cgu_rag.agente.modelo import criar_modelo
from cgu_rag.agente.skills import resumir_trecho

# ── Configuração da página ─────────────────────────────────────
st.set_page_config(
    page_title="Assistente CGU — PAD e PAR",
    page_icon="⚖️",
    layout="centered",
)

st.title("⚖️ Assistente CGU")
st.caption("Consultas sobre Processo Administrativo Disciplinar (PAD) e de Responsabilização (PAR)")

# ── Estado da sessão ───────────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historico" not in st.session_state:
    st.session_state.historico = []  # lista de (role, texto)
if "grafo" not in st.session_state:
    with st.spinner("Carregando modelo e base de documentos..."):
        modelo = criar_modelo()
        buscador_base, log = criar_buscador(), []

        def buscador(q, k):
            linhas = buscador_base(q, k)
            log.append(linhas)
            return linhas

        ferramentas = [criar_ferramenta_consulta(buscador)] + criar_ferramentas_web() + [resumir_trecho]
        st.session_state.grafo = criar_grafo(modelo, ferramentas=ferramentas)
        st.session_state.log = log

# ── Histórico ─────────────────────────────────────────────────
for role, msg in st.session_state.historico:
    with st.chat_message(role):
        st.markdown(msg)

# ── Entrada do usuário ─────────────────────────────────────────
pergunta = st.chat_input("Digite sua pergunta sobre PAD ou PAR...")

if pergunta:
    st.session_state.historico.append(("user", pergunta))
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando base de documentos..."):
            resposta, estado = conversar(
                st.session_state.grafo,
                pergunta,
                st.session_state.thread_id,
            )

        st.markdown(resposta)

        # Metadados colapsáveis
        ferramentas_usadas = estado.get("ferramentas", [])
        skills_usadas = estado.get("skills", [])
        truncada = estado.get("truncada", False)

        if ferramentas_usadas or skills_usadas or truncada:
            with st.expander("ℹ️ Detalhes da resposta", expanded=False):
                if ferramentas_usadas:
                    st.write("**Consultas realizadas:**")
                    for c in ferramentas_usadas:
                        st.code(f"{c['nome']}: {c['args']}", language="text")
                if skills_usadas:
                    st.write(f"**Skills ativas:** {', '.join(skills_usadas)}")
                if truncada:
                    st.warning("⚠️ Resposta truncada (limite de tokens atingido).")

    st.session_state.historico.append(("assistant", resposta))

# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurações")
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}...`")

    if st.button("🗑️ Nova conversa"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.historico = []
        st.rerun()

    st.divider()
    st.markdown(
        "**Ferramentas disponíveis:**\n"
        "- 🔍 `consultar_base` — corpus CGU local\n"
        "- 🌐 `buscar_web` — DuckDuckGo\n"
        "- 🔗 `buscar_url` — leitura de URLs\n"
        "- 📝 `resumir_trecho` — resumo em bullets\n"
        "- 🛡️ `filtro_prompt` — guardrail de entrada"
    )
    st.divider()
    st.markdown("**Corpus:** 6 PDFs · 1567 trechos")
    st.markdown("**Modelo:** `gemma4:e4b` (Ollama local)")
