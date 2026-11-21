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

import re
import uuid

SKILLS = {"resumir_trecho"}
_RESUMO = re.compile(r"\bresum", re.IGNORECASE)

PROMPT_SISTEMA = (
    "Assistente CGU: PAD e PAR. "
    "Responda em português, direto, máximo 3 frases. "
    "Se não souber, diga que não sabe."
)

PROMPT_RAG = (
    "Assistente CGU: PAD e PAR. Responda em português, máximo 3 frases, sem introdução.\n"
    "REGRAS DE ANTI-INVENÇÃO (prioridade máxima):\n"
    "- Use SOMENTE informação que aparece literalmente no resultado de uma ferramenta neste turno. "
    "Nunca use conhecimento próprio para fatos, números ou nomes.\n"
    "- NUNCA invente nem complete de memória: CNPJ, CPF, valores, datas, números de processo, "
    "nomes, artigos de lei ou prazos. Se o dado não está no resultado, diga que não encontrou.\n"
    "- Se o resultado da ferramenta for parcial ou ambíguo, diga o que foi encontrado e o que faltou. Não preencha lacunas.\n"
    "- Resultado de buscar_web são apenas snippets: não os trate como confirmação definitiva; "
    "para detalhes, use buscar_url na página citada.\n"
    "- Se uma ferramenta der erro ou vier vazia, informe a falha; não responda como se tivesse achado.\n"
    "- Não responda com base em perguntas ou respostas anteriores se o dado não estiver nos resultados deste turno; consulte de novo.\n"
    "REGRAS DE USO DAS FERRAMENTAS:\n"
    "- Perguntas jurídicas: use consultar_base SEMPRE. Se falhar, reformule (sinônimos) até 3x.\n"
    "- Sem resultado no corpus: use buscar_web com 2 a 4 palavras-chave. Se usuário der URL: use buscar_url.\n"
    "- Sanções/CEIS/CNEP/CEPIM: transparencia_sancoes. PEP: transparencia_pep.\n"
    "- Despesas federais: transparencia_despesas_favorecido. CNPJ informado: cnpj_consultar ou cnpj_processos.\n"
    "- Não existe ferramenta para descobrir CNPJ a partir do nome da empresa: "
    "se pedirem isso, só cite um CNPJ se aparecer literalmente em um resultado; senão peça o número ao usuário.\n"
    "- NÃO inclua fonte/página (o sistema acrescenta).\n"
    "- Sem evidência após consultas: responda exatamente 'Não encontrei nos documentos.'\n"
    "- Pedido de resumo ('resuma', 'resumo'): consultar_base e depois resumir_trecho; use os bullets como resposta.\n"
    "- Saudações: 1 frase, sem consultar.\n"
    "Skills disponíveis (use sob demanda):\n"
    "- resumir_trecho: quando o usuário pedir resumo ou o trecho for longo.\n"
    "- filtro_prompt: aplicado automaticamente na entrada.\n"
)

MAX_MSGS = 10       # mensagens recentes enviadas ao modelo (o contexto do modelo local e limitado)
MAX_CONSULTAS = 6   # consultas por turno; depois disso o modelo e obrigado a responder
MAX_TOKENS_SAIDA = int(os.getenv("LLM_MAX_TOKENS", "500"))  # D-18: limite explicito, nunca corte silencioso


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]  # historico da conversa
    bloqueado: str        # motivo da recusa; vazio se liberado
    ferramentas: list     # ferramentas chamadas neste turno (a interface exibe)
    skills: list          # skills carregadas neste turno (a interface exibe)
    truncada: bool        # a resposta bateu no limite de tokens de saida (D-18)
    pedir_resumo: bool    # o usuario pediu resumo: forca a skill resumir_trecho

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
    status: dict = {}
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, ToolMessage):
            status[m.tool_call_id] = getattr(m, "status", "success")
        if isinstance(m, AIMessage):
            chamadas = [
                {"nome": c["name"], "args": c["args"], "status": status.get(c["id"], "success")}
                for c in m.tool_calls
            ] + chamadas
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
    import sys
    print(f"[DEBUG] criar_grafo() iniciada com {len(ferramentas or [])} ferramentas", file=sys.stderr)
    
    ferramentas = ferramentas or []
    print(f"[DEBUG] ferramentas: {[f.name for f in ferramentas]}", file=sys.stderr)
    
    sem_ferramentas = _limitar(modelo, max_tokens)
    print(f"[DEBUG] sem_ferramentas criado: {sem_ferramentas}", file=sys.stderr)
    
    if ferramentas:
        try:
            print(f"[DEBUG] chamando modelo.bind_tools()...", file=sys.stderr)
            bound = modelo.bind_tools(ferramentas)
            print(f"[DEBUG] bind_tools() retornou: {bound}", file=sys.stderr)
            com_ferramentas = _limitar(bound, max_tokens)
            print(f"[DEBUG] com_ferramentas criado: {com_ferramentas}", file=sys.stderr)
        except Exception as e:
            print(f"[DEBUG] ERRO em bind_tools: {type(e).__name__}: {e}", file=sys.stderr)
            raise
    else:
        com_ferramentas = sem_ferramentas
    
    prompt = prompt or (PROMPT_RAG if ferramentas else PROMPT_SISTEMA)
    
    def entrada(estado: Estado) -> dict:
        msg = estado["messages"][-1]
        vazio = _humana_vazia(msg)
        if vazio:
            return {"bloqueado": "mensagem vazia", "ferramentas": [], "skills": [], "truncada": False}
        from .skills import filtro_prompt
        bloqueio = filtro_prompt(str(msg.content))
        if bloqueio:
            return {"bloqueado": bloqueio, "ferramentas": [], "skills": ["filtro_prompt"], "truncada": False}
        return {"bloqueado": "", "ferramentas": [], "skills": [], "truncada": False}
    
    def responder(estado: Estado) -> dict:
        msgs = estado["messages"]
        usar = com_ferramentas if consultas_no_turno(msgs) < max_consultas else sem_ferramentas
        return {"messages": [usar.invoke([SystemMessage(prompt)] + recentes(msgs, max_msgs))]}
    
    def saida(estado: Estado) -> dict:
        msgs = estado["messages"]
        chamadas = chamadas_do_turno(msgs)
        out: dict = {
            "ferramentas": chamadas,
            "skills": [c["nome"] for c in chamadas if c["nome"] in SKILLS],
        }
        if estado.get("bloqueado"):
            out["skills"] = ["filtro_prompt"]
            out["messages"] = [AIMessage(f"Não posso processar: {estado['bloqueado']}.")]
            return out
        ultima = msgs[-1]
        if isinstance(ultima, AIMessage) and not ultima.tool_calls:
            meta = ultima.response_metadata or {}
            out["truncada"] = meta.get("finish_reason") == "length"
            texto = guardrail_saida(str(ultima.content))
            if ferramentas:
                texto = anexar_fonte(texto, trechos_do_turno(msgs))
            if texto != str(ultima.content):
                out["messages"] = [AIMessage(content=texto, id=ultima.id, response_metadata=meta)]
        return out
    
    def rota_entrada(estado: Estado) -> str:
        return "saida" if estado.get("bloqueado") else "responder"
    
    def rota_responder(estado: Estado) -> str:
        return "ferramentas" if getattr(estado["messages"][-1], "tool_calls", None) else "saida"
    
    print(f"[DEBUG] criando StateGraph...", file=sys.stderr)
    g = StateGraph(Estado)
    g.add_node("entrada", entrada)
    g.add_node("responder", responder)
    g.add_node("saida", saida)
    g.add_edge(START, "entrada")
    g.add_conditional_edges("entrada", rota_entrada, {"responder": "responder", "saida": "saida"})
    
    if ferramentas:
        print(f"[DEBUG] adicionando ToolNode com {len(ferramentas)} ferramentas...", file=sys.stderr)
        g.add_node("ferramentas", ToolNode(ferramentas, handle_tool_errors=True))
        g.add_conditional_edges("responder", rota_responder, {"ferramentas": "ferramentas", "saida": "saida"})
        g.add_edge("ferramentas", "responder")
    else:
        g.add_edge("responder", "saida")
    
    g.add_edge("saida", END)
    
    print(f"[DEBUG] compilando grafo...", file=sys.stderr)
    try:
        compiled = g.compile(checkpointer=checkpointer or MemorySaver())
        print(f"[DEBUG] g.compile() retornou: {compiled}", file=sys.stderr)
        print(f"[DEBUG] tipo: {type(compiled)}", file=sys.stderr)
        return compiled
    except Exception as e:
        print(f"[DEBUG] ERRO em g.compile(): {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise

def guardrail_saida(resposta: str) -> str:
    """Bloqueia resposta vazia ou sem conteúdo útil."""
    texto = resposta.strip() if resposta else ""
    if len(texto) < 10:
        return "⚠️ Não foi possível gerar uma resposta. Tente reformular a pergunta."
    return texto


def conversar(grafo, texto: str, thread_id: str) -> tuple[str, dict]:
    cfg = {"configurable": {"thread_id": thread_id}}
    out = grafo.invoke({"messages": [HumanMessage(texto)]}, cfg)
    return str(out["messages"][-1].content), out
