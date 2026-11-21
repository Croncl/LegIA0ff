"""
UI Streamlit (R12) — Assistente Legislação Offline.
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
from ui_grafo import renderizar_mapa_conhecimento

# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Assistente Legislação Offline",
    page_icon="⚖️",
    layout="wide",
)
aplicar_estilo()

# ---------------------------------------------------------------------------
HISTORICO_DIR = Path("data/historico_chats")
HISTORICO_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Inicialização do session_state
# ---------------------------------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historico" not in st.session_state:
    st.session_state.historico = []
if "status_chats" not in st.session_state:      # <--- NOVO
    st.session_state.status_chats = {}          # <--- NOVO
if "retry" not in st.session_state:
    st.session_state.retry = False
if "pergunta_retry" not in st.session_state:
    st.session_state.pergunta_retry = None

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
# Persistência
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
# Ações
# ---------------------------------------------------------------------------
def acao_nova_conversa() -> None:
    salvar_historico()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.historico = []
    st.session_state.retry = False
    st.session_state.pergunta_retry = None
    st.rerun()


def excluir_chat(thread_id: str) -> None:
    arq = HISTORICO_DIR / f"{thread_id[:8]}.json"
    arq.unlink(missing_ok=True)
    if st.session_state.thread_id == thread_id:
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.historico = []


def acao_renderizar_lista_chats() -> None:
    chats = carregar_chats_salvos()
    if not chats:
        st.caption("Nenhum chat salvo ainda.")
        return
    
    # Pega o status atual do dicionário
    status_dict = st.session_state.get("status_chats", {})
    
    for chat in chats:
        tid = chat['thread_id']
        esta_rodando = status_dict.get(tid) == "processing"
        
        col_chat, col_del = st.columns([5, 1])
        
        with col_chat:
            # Se estiver rodando, adiciona um ícone de "carregando" e desabilita o botão
            prefixo = "⏳ " if esta_rodando else ""
            label = f"{prefixo}{chat['preview']} ({chat['n_msgs']} msgs)"
            
            # Desabilita o botão se este chat específico estiver processando
            if st.button(
                label[:50], 
                key=f"load_{tid}", 
                use_container_width=True,
                disabled=esta_rodando,
                help="Aguarde o processamento terminar..." if esta_rodando else None
            ):
                salvar_historico()
                carregar_chat(tid)
                st.rerun()
                
            # Adiciona um pequeno texto embaixo se estiver rodando
            if esta_rodando:
                st.markdown(
                    '<div style="font-size:0.75rem; color: #6B97FF; margin-top:-10px; margin-bottom:5px;">'
                    '🔄 Processando...</div>', 
                    unsafe_allow_html=True
                )
                
        with col_del:
            # Não permite excluir um chat que está rodando
            if st.button("🗑", key=f"del_{tid}", help="Excluir este chat", disabled=esta_rodando):
                excluir_chat(tid)
                st.rerun()


# ---------------------------------------------------------------------------
# Layout
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

    # --- INDICADOR NO CHAT ATUAL ---
    current_thread = st.session_state.thread_id
    status_atual = st.session_state.status_chats.get(current_thread, "idle")
    esta_processando = (status_atual == "processing")

    if esta_processando:
        # Cria um container visual chamativo
        st.markdown(
            f"""
            <div style="
                background: rgba(107, 151, 255, 0.15);
                border: 1px solid rgba(107, 151, 255, 0.4);
                border-radius: 8px;
                padding: 10px 15px;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
                color: var(--cg-text);
                font-weight: 500;
            ">
                <div class="spinner-pulsante" style="
                    width: 12px; height: 12px; 
                    background-color: #6B97FF; 
                    border-radius: 50%;
                    animation: pulsar 1.5s infinite;
                "></div>
                O Assistente está analisando os documentos... Por favor, aguarde.
            </div>
            <style>
                @keyframes pulsar {{
                    0% {{ transform: scale(0.8); opacity: 0.5; }}
                    50% {{ transform: scale(1.2); opacity: 1; }}
                    100% {{ transform: scale(0.8); opacity: 0.5; }}
                }}
            </style>
            """,
            unsafe_allow_html=True
        )
    # ---------------------------------

    # 🧠 MAPA DE CONHECIMENTO
    renderizar_mapa_conhecimento(st.session_state.historico, top_n=40)

    # Histórico
    for msg in st.session_state.historico:
        renderizar_mensagem(msg)

    # --- LÓGICA DE STATUS POR CHAT ---
    current_thread = st.session_state.thread_id
    status_atual = st.session_state.status_chats.get(current_thread, "idle")
    esta_processando = (status_atual == "processing")

    # Botão retry — aparece só quando a última mensagem é do assistente E o chat está livre
    if (
        st.session_state.historico
        and st.session_state.historico[-1]["role"] == "assistant"
        and not esta_processando
    ):
        if st.button("🔄 Tentar novamente", key="btn_retry"):
            ultima_pergunta = next(
                (m["texto"] for m in reversed(st.session_state.historico) if m["role"] == "user"),
                None,
            )
            st.session_state.historico.pop()
            st.session_state.pergunta_retry = ultima_pergunta
            st.rerun()

    # Input: desabilita APENAS se o chat atual estiver processando
    pergunta = st.chat_input(
        "Digite sua pergunta sobre PAD ou PAR...",
        disabled=esta_processando,
    )

    # Se vier do retry, usa a pergunta recuperada
    if st.session_state.pergunta_retry:
        pergunta = st.session_state.pergunta_retry
        st.session_state.pergunta_retry = None

    # --- PROCESSAMENTO DA PERGUNTA ---
    if pergunta and not esta_processando:
        # 1. Marca o status deste chat como processando
        st.session_state.status_chats[current_thread] = "processing"
        
        # 2. Adiciona a mensagem do usuário
        ts = datetime.now().isoformat(timespec="seconds")
        st.session_state.historico.append({"role": "user", "texto": pergunta, "ts": ts})
        with st.chat_message("user"):
            st.markdown(pergunta)

        # 3. Cria o placeholder do assistente e roda o spinner
        with st.chat_message("assistant"):
            placeholder_resposta = st.empty()
            with placeholder_resposta.container():
                with st.spinner("Analisando documentos e consultando ferramentas..."):
                    resposta, estado = conversar(
                        st.session_state.grafo,
                        pergunta,
                        current_thread,
                    )
            
            # 4. Substitui o spinner pela resposta final
            placeholder_resposta.markdown(resposta)
            
            meta_msg = {
                "ferramentas": estado.get("ferramentas", []),
                "skills": estado.get("skills", []),
                "truncada": estado.get("truncada", False),
            }
            renderizar_detalhes_execucao(meta_msg)

        # 5. Salva no histórico e libera o chat
        st.session_state.historico.append({
            "role": "assistant",
            "texto": resposta,
            "ts": ts,
            "meta": meta_msg,
        })
        salvar_historico()
        
        # Limpa o status deste chat específico
        st.session_state.status_chats[current_thread] = "idle"
        
        # Força atualização para habilitar o input novamente
        st.rerun()