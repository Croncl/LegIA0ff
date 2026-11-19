"""Grafo LangGraph do assistente: estado, nos, arestas e memoria por conversa (D-14, D-15, D-18).

Fluxo:  entrada -> (bloqueado? saida : responder) ; responder -> (pediu ferramenta? ferramentas -> responder : saida)
- entrada:     normaliza o turno e zera ferramentas/skills usadas (ponto do guardrail de entrada, R11)
- responder:   o modelo decide: responder ou chamar a ferramenta de consulta (RAG agentico, D-15)
- ferramentas: executa a consulta; o resultado volta ao modelo, que pode reformular e consultar de novo
- saida:       registra as ferramentas do turno, anexa a fonte e a pagina (D-18) e entrega a resposta ou a
               recusa (guardrail de saida, R11)
Memoria: checkpointer por thread_id (uma conversa = uma thread).
"""
from __future__ import annotations

import os
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .citacao import anexar_fonte

PROMPT_SISTEMA = (
    "Voce e um assistente sobre processos de correicao da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilizacao (PAR). Responda em portugues, de forma direta, em no "
    "maximo 3 frases. Se nao souber, diga que nao sabe."
)
PROMPT_RAG = (
    "Você é um assistente sobre processos de correição da CGU: processo administrativo disciplinar (PAD) "
    "e processo administrativo de responsabilização (PAR). Responda em português.\n"
    "Para qualquer pergunta sobre normas, servidores públicos, processos disciplinares, responsabilização de "
    "empresas, licitações, prazos, ritos ou conceitos jurídicos, SEMPRE use a ferramenta consultar_base antes "
    "de responder. Se os trechos não responderem, reformule a consulta (outros termos, sinônimos, termo "
    "técnico) e consulte de novo, no máximo 3 consultas.\n"
    "Se consultar_base não trouxer resultado, use buscar_web para procurar normas na internet. Se o usuário fornecer uma URL, use buscar_url.\n"
    "Para sanções (CEIS/CNEP/CEPIM) use transparencia_sancoes; para PEP use transparencia_pep; para despesas federais use transparencia_despesas_favorecido; para dados de CNPJ use cnpj_consultar; para processos judiciais use cnpj_processos.\n"
    "Responda SOMENTE com base nos trechos, de forma direta: no máximo 3 frases, sem introdução e sem repetir "
    "a pergunta. NÃO escreva fonte nem página: o sistema as acrescenta.\n"
    "Se, depois de consultar, não houver evidência, responda apenas: Não encontrei nos documentos.\n"
    "Para saudações e conversa simples, responda em uma frase, sem consultar."
)
MAX_MSGS = 10       # mensagens recentes enviadas ao modelo (o contexto do modelo local e limitado)
MAX_CONSULTAS = 3   # consultas por turno; depois disso o modelo e obrigado a responder
MAX_TOKENS_SAIDA = int(os.getenv("LLM_MAX_TOKENS", "300"))  # D-18: limite explicito, nunca corte silencioso


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # historico da conversa
    bloqueado: str        # motivo da recusa; vazio se liberado
    ferramentas: list     # ferramentas chamadas neste turno (a interface exibe)
    skills: list          # skills carregadas neste turno (a interface exibe)
    truncada: bool        # a resposta bateu no limite de tokens de saida (D-18)


def _humana_vazia(m) -> bool:
    return isinstance(m, HumanMessage) and not str(m.content).strip()


def recentes(mensagens: list, max_msgs: int) -> list:
    """Historico enviado ao modelo: sem mensagens vazias do usuario e, nos turnos ANTERIORES, sem chamadas e
    resultados de ferramenta (so pergunta e resposta final; o resultado das consultas pesa no contexto).
    O turno atual fica completo. A lista comeca sempre por uma mensagem do usuario."""
    msgs = [m for m in mensagens if not _humana_vazia(m)]
    ult = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
    antes = [m for m in msgs[:ult]
             if not isinstance(m, ToolMessage) and not (isinstance(m, AIMessage) and m.tool_calls)]
    atual = msgs[ult:]
    espaco = max(max_msgs - len(atual), 0)  # o turno atual nunca e cortado
    sel = (antes[-espaco:] if espaco else []) + atual
    while sel and not isinstance(sel[0], HumanMessage):
        sel.pop(0)
    return sel


def consultas_no_turno(mensagens: list) -> int:
    n = 0
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        n += isinstance(m, ToolMessage)
    return n


def chamadas_do_turno(mensagens: list) -> list[dict]:
    chamadas: list[dict] = []
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage):
            chamadas = [{"nome": c["name"], "args": c["args"]} for c in m.tool_calls] + chamadas
    return chamadas


def trechos_do_turno(mensagens: list) -> list[dict]:
    """Trechos recuperados no turno atual (do artefato das ToolMessages), consulta mais recente primeiro."""
    por_consulta: list[list] = []
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, ToolMessage):
            por_consulta.append(list(getattr(m, "artifact", None) or []))
    return [t for consulta in por_consulta for t in consulta]


def _limitar(modelo, max_tokens):
    """Fixa o limite de tokens de saida; modelos sem `bind` (dublês de teste) passam direto."""
    return modelo.bind(max_tokens=max_tokens) if max_tokens and hasattr(modelo, "bind") else modelo


def criar_grafo(modelo, max_msgs: int = MAX_MSGS, checkpointer=None, ferramentas: list | None = None,
                max_consultas: int = MAX_CONSULTAS, prompt: str | None = None,
                max_tokens: int | None = MAX_TOKENS_SAIDA):
    """`modelo` e qualquer objeto com invoke(mensagens) -> AIMessage (e bind_tools, se houver ferramentas)."""
    ferramentas = ferramentas or []
    sem_ferramentas = _limitar(modelo, max_tokens)
    com_ferramentas = _limitar(modelo.bind_tools(ferramentas), max_tokens) if ferramentas else sem_ferramentas
    prompt = prompt or (PROMPT_RAG if ferramentas else PROMPT_SISTEMA)

    def entrada(estado: Estado) -> dict:
        vazio = _humana_vazia(estado["messages"][-1])
        return {"bloqueado": "mensagem vazia" if vazio else "", "ferramentas": [], "skills": [], "truncada": False}

    def responder(estado: Estado) -> dict:
        msgs = estado["messages"]
        usar = com_ferramentas if consultas_no_turno(msgs) < max_consultas else sem_ferramentas  # limite: sem ferramenta
        return {"messages": [usar.invoke([SystemMessage(prompt)] + recentes(msgs, max_msgs))]}

    def saida(estado: Estado) -> dict:
        msgs = estado["messages"]
        out: dict = {"ferramentas": chamadas_do_turno(msgs)}
        if estado.get("bloqueado"):
            out["messages"] = [AIMessage(f"Nao posso processar: {estado['bloqueado']}.")]
            return out
        ultima = msgs[-1]
        if isinstance(ultima, AIMessage) and not ultima.tool_calls:
            meta = ultima.response_metadata or {}
            out["truncada"] = meta.get("finish_reason") == "length"
            if ferramentas:  # D-18: fonte e pagina anexadas pelo sistema, a partir dos trechos recuperados
                texto = str(ultima.content)
                novo = anexar_fonte(texto, trechos_do_turno(msgs))
                if novo != texto:
                    out["messages"] = [AIMessage(content=novo, id=ultima.id, response_metadata=meta)]
        return out

    def rota_entrada(estado: Estado) -> str:
        return "saida" if estado.get("bloqueado") else "responder"

    def rota_responder(estado: Estado) -> str:
        return "ferramentas" if getattr(estado["messages"][-1], "tool_calls", None) else "saida"

    g = StateGraph(Estado)
    g.add_node("entrada", entrada)
    g.add_node("responder", responder)
    g.add_node("saida", saida)
    g.add_edge(START, "entrada")
    g.add_conditional_edges("entrada", rota_entrada, {"responder": "responder", "saida": "saida"})
    if ferramentas:
        g.add_node("ferramentas", ToolNode(ferramentas, handle_tool_errors=True))
        g.add_conditional_edges("responder", rota_responder, {"ferramentas": "ferramentas", "saida": "saida"})
        g.add_edge("ferramentas", "responder")
    else:
        g.add_edge("responder", "saida")
    g.add_edge("saida", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())


def conversar(grafo, texto: str, thread_id: str) -> tuple[str, dict]:
    """Um turno. Devolve (resposta, estado final). O thread_id identifica a conversa."""
    from .skills import filtro_prompt  # R11: guardrail de entrada
    bloqueio = filtro_prompt(texto)
    if bloqueio:
        return bloqueio, {"bloqueado": "prompt longo", "ferramentas": [], "skills": ["filtro_prompt"], "truncada": False, "messages": [HumanMessage(texto), AIMessage(bloqueio)]}
    cfg = {"configurable": {"thread_id": thread_id}}
    out = grafo.invoke({"messages": [HumanMessage(texto)]}, cfg)
    return str(out["messages"][-1].content), out
