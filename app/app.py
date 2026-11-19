"""
UI Streamlit (R12) — Assistente CGU RAG (PAD e PAR).
Uso (na raiz do projeto):
    streamlit run app/app.py
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta
from cgu_rag.agente.grafo import conversar, criar_grafo
from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web
from cgu_rag.agente.mcp_transparencia import criar_ferramentas_transparencia
from cgu_rag.agente.modelo import criar_modelo
from cgu_rag.agente.skills import resumir_trecho

from ui_estilo import (
    aplicar_estilo,
    renderizar_cabecalho,
    renderizar_detalhes_execucao,
    renderizar_mensagem,
    renderizar_sidebar_config,
)
from ui_grafo import renderizar_mapa_conhecimento   # <-- NOVO

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Assistente CGU — PAD e PAR",
    page_icon="⚖️",
    layout="wide",
)
aplicar_estilo()

# ---------------------------------------------------------------------------
HISTORICO_DIR = Path("data/historico_chats")
HISTORICO_DIR.mkdir(parents=True, exist_ok=True)

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historico" not in st.session_state:
    st.session_state.historico = []
if "processando" not in st.session_state:
    st.session_state.processando = False
if "grafo" not in st.session_state:
    with st.spinner("Carregando modelo e base de documentos..."):
        modelo = criar_modelo()
        buscador_base = criar_buscador()
        log: list = []

        def buscador(q: str, k: int):
            linhas = buscador_base(q, k)
            log.append(linhas)
            return linhas

        ferramentas_lista = (
            [criar_ferramenta_consulta(buscador)]
            + criar_ferramentas_web()
            + criar_ferramentas_transparencia()
            + [resumir_trecho]
        )

        st.session_state.grafo = criar_grafo(modelo, ferramentas=ferramentas_lista)
        st.session_state.log = log
        st.session_state.ferramentas_nomes = [f.name for f in ferramentas_lista] + ["filtro_prompt"]

# ---------------------------------------------------------------------------
def salvar_historico() -> None:
    if not st.session_state.historico:
        return
    arq = HISTORICO_DIR / f"{st.session_state.thread_id[:8]}.json"
    payload = {
        "thread_id": st.session_state.thread_id,
        "inicio": st.session_state.historico[0].get("ts", ""),
        "mensagens": st.session_state.historico,
    }
    arq.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar_chats_salvos() -> list[dict]:
    chats: list[dict] = []
    for arq in sorted(HISTORICO_DIR.glob("*.json"), reverse=True)[:20]:
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
            msgs = d.get("mensagens", [])
            primeira = next((m["texto"] for m in msgs if m["role"] == "user"), "—")
            chats.append({
                "thread_id": d.get("thread_id", arq.stem),
                "inicio": d.get("inicio", ""),
                "preview": primeira[:60],
                "n_msgs": len(msgs),
            })
        except Exception:
            continue
    return chats


def carregar_chat(thread_id: str) -> None:
    arq = HISTORICO_DIR / f"{thread_id[:8]}.json"
    if arq.exists():
        d = json.loads(arq.read_text(encoding="utf-8"))
        st.session_state.thread_id = d["thread_id"]
        st.session_state.historico = d.get("mensagens", [])


# ---------------------------------------------------------------------------
def acao_nova_conversa() -> None:
    salvar_historico()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.historico = []
    st.session_state.processando = False
    st.rerun()


def excluir_chat(thread_id: str) -> None:
    arq = HISTORICO_DIR / f"{thread_id[:8]}.json"
    arq.unlink(missing_ok=True)
    if st.session_state.thread_id == thread_id:
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.historico = []
        st.session_state.processando = False


def acao_renderizar_lista_chats() -> None:
    chats = carregar_chats_salvos()
    if not chats:
        st.caption("Nenhum chat salvo ainda.")
        return
    for chat in chats:
        col_chat, col_del = st.columns([5, 1])
        with col_chat:
            label = f"{chat['preview']} ({chat['n_msgs']} msgs)"
            if st.button(label[:50], key=f"load_{chat['thread_id']}", use_container_width=True):
                salvar_historico()
                carregar_chat(chat["thread_id"])
                st.rerun()
        with col_del:
            if st.button("🗑", key=f"del_{chat['thread_id']}", help="Excluir este chat"):
                excluir_chat(chat["thread_id"])
                st.rerun()


# ---------------------------------------------------------------------------
col_main, col_side = st.columns([3, 1])

with col_side:
    renderizar_sidebar_config(
        thread_id=st.session_state.thread_id,
        ferramentas_nomes=st.session_state.get("ferramentas_nomes", []),
        on_nova_conversa=acao_nova_conversa,
        on_carregar_chat=acao_renderizar_lista_chats,
    )

with col_main:
    renderizar_cabecalho()

    # 🧠 MAPA DE CONHECIMENTO — cresce com as mensagens
    renderizar_mapa_conhecimento(st.session_state.historico, top_n=40)

    # Histórico
    for msg in st.session_state.historico:
        renderizar_mensagem(msg)

    # Input
    pergunta = st.chat_input(
        "Digite sua pergunta sobre PAD ou PAR...",
        disabled=st.session_state.processando,
    )

    if pergunta and not st.session_state.processando:
        st.session_state.processando = True
        ts = datetime.now().isoformat(timespec="seconds")

        st.session_state.historico.append({"role": "user", "texto": pergunta, "ts": ts})
        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            with st.spinner("Consultando..."):
                resposta, estado = conversar(
                    st.session_state.grafo,
                    pergunta,
                    st.session_state.thread_id,
                )
            st.markdown(resposta)
            meta_msg = {
                "ferramentas": estado.get("ferramentas", []),
                "skills": estado.get("skills", []),
                "truncada": estado.get("truncada", False),
            }
            renderizar_detalhes_execucao(meta_msg)

        st.session_state.historico.append({
            "role": "assistant",
            "texto": resposta,
            "ts": ts,
            "meta": meta_msg,
        })
        salvar_historico()
        st.session_state.processando = False
        st.rerun()