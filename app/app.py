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
from langchain_core.messages import HumanMessage, RemoveMessage

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta
from cgu_rag.agente.grafo import conversar, criar_grafo
from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web
from cgu_rag.agente.mcp_transparencia import criar_ferramentas_transparencia
from cgu_rag.agente.modelo import criar_modelo
from cgu_rag.agente.skills import resumir_trecho, resumir_conversa
from ui_estilo import (
    aplicar_estilo,
    renderizar_cabecalho,
    renderizar_detalhes_execucao,
    renderizar_mensagem,
    renderizar_sidebar_config,
    renderizar_trace,
)
from ui_grafo import renderizar_mapa_conhecimento



@st.cache_resource(show_spinner="Carregando modelo e base de documentos...")
def _inicializar_agente():
    """Cria o grafo uma única vez (cache do Streamlit). Retorna (grafo, log, nomes_ferramentas)."""
    try:
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
            + [resumir_trecho, resumir_conversa]  # <-- adicionar
        )
        
        # Diagnóstico granular
        try:
            grafo = criar_grafo(modelo, ferramentas=ferramentas_lista)
            if grafo is None:
                raise RuntimeError("criar_grafo() retornou None")
        except Exception as e:
            import traceback
            st.error(f"❌ Erro ao criar o grafo: {type(e).__name__}: {e}")
            st.code(traceback.format_exc(), language="text")
            raise
        
        nomes = [f.name for f in ferramentas_lista] + ["filtro_prompt"]
        return grafo, log, nomes
    except Exception as e:
        import traceback
        st.error(f"❌ Erro na inicialização: {type(e).__name__}: {e}")
        st.code(traceback.format_exc(), language="text")
        raise

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
# Inicialização do session_state (Garantia absoluta de existência)
# ---------------------------------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historico" not in st.session_state:
    st.session_state.historico = []
if "status_chats" not in st.session_state:
    st.session_state.status_chats = {}
if "retry" not in st.session_state:
    st.session_state.retry = False
if "pergunta_retry" not in st.session_state:
    st.session_state.pergunta_retry = None

if "corpus_stats" not in st.session_state:
    try:
        from cgu_rag.busca import abrir_db
        con = abrir_db()
        n_trechos = con.execute("SELECT COUNT(*) FROM chunks WHERE tipo != 'indice'").fetchone()[0]
        n_docs = con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        st.session_state.corpus_stats = {"docs": n_docs, "trechos": n_trechos}
        con.close()
    except Exception:
        st.session_state.corpus_stats = {"docs": "?", "trechos": "?"}

# Inicialização robusta do agente via cache
if st.session_state.get("grafo") is None:
    try:
        _grafo, _log, _nomes = _inicializar_agente()
        st.session_state.grafo = _grafo
        st.session_state.log = _log
        st.session_state.ferramentas_nomes = _nomes
    except Exception as e:
        import traceback
        st.error(f"❌ Falha ao inicializar o agente: {type(e).__name__}: {e}")
        st.code(traceback.format_exc(), language="text")
        st.stop()

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

def excluir_turno(idx_user: int) -> None:
    """Remove a N-ésima pergunta (0-based) e sua resposta, na tela e no grafo."""
    hist = st.session_state.historico
    pos = [i for i, m in enumerate(hist) if m["role"] == "user"]
    ini = pos[idx_user]
    fim = pos[idx_user + 1] if idx_user + 1 < len(pos) else len(hist)
    del hist[ini:fim]

    cfg = {"configurable": {"thread_id": st.session_state.thread_id}}
    try:
        msgs = st.session_state.grafo.get_state(cfg).values.get("messages", [])
        humanas = [i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)]
        if idx_user < len(humanas):
            a = humanas[idx_user]
            b = humanas[idx_user + 1] if idx_user + 1 < len(humanas) else len(msgs)
            st.session_state.grafo.update_state(
                cfg, {"messages": [RemoveMessage(id=m.id) for m in msgs[a:b]]}
            )
    except Exception:
        pass
    salvar_historico()

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

# Sidebar: renderizar_sidebar_config() já utiliza with st.sidebar internamente
renderizar_sidebar_config(
    thread_id=st.session_state.thread_id,
    ferramentas_nomes=st.session_state.get("ferramentas_nomes", []),
    on_nova_conversa=acao_nova_conversa,
    on_carregar_chat=acao_renderizar_lista_chats,
    corpus_stats=st.session_state.corpus_stats,
)

# Botões de emergência na sidebar
with st.sidebar:

    # Desbloqueia o chat atual
    if st.session_state.status_chats.get(st.session_state.thread_id) == "processing":
        if st.button("🔓 Desbloquear chat", key="btn_desbloquear"):
            st.session_state.status_chats[st.session_state.thread_id] = "idle"
            st.rerun()

    # Desbloqueia todos os chats travados
    chats_travados = [
        tid
        for tid, status in st.session_state.status_chats.items()
        if status == "processing"
    ]

    if chats_travados:
        if st.button(
            f"🔓 Desbloquear todos ({len(chats_travados)})",
            key="btn_desbloquear_todos",
        ):
            for tid in chats_travados:
                st.session_state.status_chats[tid] = "idle"
            st.rerun()


# ---------------------------------------------------------------------------
# Área principal
# ---------------------------------------------------------------------------

renderizar_cabecalho()

# --- INDICADOR NO CHAT ATUAL ---
current_thread = st.session_state.thread_id
status_atual = st.session_state.status_chats.get(current_thread, "idle")
esta_processando = status_atual == "processing"

if esta_processando:
    st.markdown(
        """
        <style>
        [data-testid="stChatInput"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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
                width: 12px;
                height: 12px;
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
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Mapa de conhecimento
# ---------------------------------------------------------------------------

renderizar_mapa_conhecimento(
    st.session_state.historico,
    top_n=40,
)


# ---------------------------------------------------------------------------
# Histórico de mensagens
# ---------------------------------------------------------------------------

idx_user = -1

for msg in st.session_state.historico:

    if msg["role"] == "user":
        idx_user += 1

        col_msg, col_x = st.columns([12, 1])

        with col_msg:
            renderizar_mensagem(msg)

        with col_x:
            if st.button(
                "✖",
                key=f"del_turno_{st.session_state.thread_id}_{idx_user}",
                help="Excluir esta pergunta e resposta (inclusive do contexto do modelo)",
                disabled=esta_processando,
            ):
                excluir_turno(idx_user)
                st.rerun()

    else:
        renderizar_mensagem(msg)


# ---------------------------------------------------------------------------
# Lógica de status por chat
# ---------------------------------------------------------------------------

current_thread = st.session_state.thread_id
status_atual = st.session_state.status_chats.get(current_thread, "idle")
esta_processando = status_atual == "processing"

if esta_processando:
    st.markdown("🔄 Analisando documentos...")


# ---------------------------------------------------------------------------
# Botão de nova tentativa
# ---------------------------------------------------------------------------

if (
    st.session_state.historico
    and st.session_state.historico[-1]["role"] == "assistant"
    and not esta_processando
):
    if st.button("🔄 Tentar novamente", key="btn_retry"):

        ultima_pergunta = next(
            (
                m["texto"]
                for m in reversed(st.session_state.historico)
                if m["role"] == "user"
            ),
            None,
        )

        # Remove a resposta anterior
        st.session_state.historico.pop()

        # Remove a pergunta anterior, que será reapresentada
        if (
            st.session_state.historico
            and st.session_state.historico[-1]["role"] == "user"
        ):
            st.session_state.historico.pop()

        st.session_state.pergunta_retry = ultima_pergunta
        st.session_state.retry_limpar = True

        st.rerun()


# ---------------------------------------------------------------------------
# Entrada do chat
# ---------------------------------------------------------------------------

pergunta = st.chat_input(
    "Digite sua pergunta sobre PAD ou PAR...",
    disabled=esta_processando,
)


# Se vier do botão de retry, recupera a pergunta anterior
if st.session_state.pergunta_retry:
    pergunta = st.session_state.pergunta_retry
    st.session_state.pergunta_retry = None


# ---------------------------------------------------------------------------
# Processamento da pergunta
# ---------------------------------------------------------------------------

if pergunta and not esta_processando:

    st.session_state.status_chats[current_thread] = "processing"

    ts = datetime.now().isoformat(timespec="seconds")

    st.session_state.historico.append(
        {
            "role": "user",
            "texto": pergunta,
            "ts": ts,
        }
    )

    try:
        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            with st.spinner(
                "Analisando documentos e consultando ferramentas..."
            ):
                resposta, estado = conversar(
                    st.session_state.grafo,
                    pergunta,
                    current_thread,
                    historico_json=st.session_state.historico,
                )

        meta_msg = {
            "ferramentas": estado.get("ferramentas", []),
            "skills": estado.get("skills", []),
            "truncada": estado.get("truncada", False),
            "bloqueado": estado.get("bloqueado", ""),
        }

        st.session_state.historico.append(
            {
                "role": "assistant",
                "texto": resposta,
                "ts": ts,
                "meta": meta_msg,
            }
        )

        salvar_historico()

    except Exception as e:

        st.session_state.historico.append(
            {
                "role": "assistant",
                "texto": f"❌ Erro: {type(e).__name__}: {e}",
                "ts": ts,
            }
        )

    finally:
        st.session_state.status_chats[current_thread] = "idle"

    st.rerun()
