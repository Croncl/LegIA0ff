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

SKILLS = {"resumir_trecho"}

_TRIGGERS_RESUMO = [
    "resuma o chat", "resuma a conversa", "resumo do chat",
    "resumo da conversa", "o que discutimos", "resume a conversa",
    "resumir conversa", "resumir o chat",
]

_SAUDACOES = {
    "oi", "olá", "ola", "tudo bem", "bom dia", "boa tarde", "boa noite",
    "obrigado", "obrigada",
}

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
    "- Pedido de resumo de trecho ('resuma esse trecho', 'resuma o documento'): "
    "consultar_base e depois resumir_trecho; use os bullets como resposta.\n"
    "- Pedido de resumo do chat ('resuma o chat', 'o que discutimos'): use resumir_conversa.\n"
    "- Saudações: 1 frase, sem consultar.\n"
    "Skills disponíveis (use sob demanda):\n"
    "- resumir_trecho: quando o usuário pedir resumo de um trecho normativo.\n"
    "- resumir_conversa: quando o usuário pedir resumo da conversa ou do chat.\n"
    "- filtro_prompt: aplicado automaticamente na entrada.\n"
)

MAX_MSGS = 10
MAX_CONSULTAS = 6
MAX_TOKENS_SAIDA = int(os.getenv("LLM_MAX_TOKENS", "500"))


class Estado(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    bloqueado: str
    ferramentas: list
    skills: list
    truncada: bool


def _humana_vazia(m) -> bool:
    return isinstance(m, HumanMessage) and not str(m.content).strip()


def recentes(mensagens: list, max_msgs: int) -> list:
    msgs = [m for m in mensagens if not _humana_vazia(m)]
    ult = max((i for i, m in enumerate(msgs) if isinstance(m, HumanMessage)), default=0)
    antes = [m for m in msgs[:ult]
             if not isinstance(m, ToolMessage) and not (isinstance(m, AIMessage) and m.tool_calls)]
    atual = msgs[ult:]
    espaco = max(max_msgs - len(atual), 0)
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
    por_consulta: list[list] = []
    for m in reversed(mensagens):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, ToolMessage):
            por_consulta.append(list(getattr(m, "artifact", None) or []))
    return [t for consulta in por_consulta for t in consulta]


def _limitar(modelo, max_tokens):
    return modelo.bind(max_tokens=max_tokens) if max_tokens and hasattr(modelo, "bind") else modelo


def guardrail_saida(resposta: str) -> str:
    """Bloqueia resposta vazia ou sem conteúdo útil."""
    texto = resposta.strip() if resposta else ""
    if len(texto) < 10:
        return "⚠️ Não foi possível gerar uma resposta. Tente reformular a pergunta."
    return texto


def criar_grafo(modelo, max_msgs: int = MAX_MSGS, checkpointer=None, ferramentas: list | None = None,
                max_consultas: int = MAX_CONSULTAS, prompt: str | None = None,
                max_tokens: int | None = MAX_TOKENS_SAIDA):
    ferramentas = ferramentas or []
    sem_ferramentas = _limitar(modelo, max_tokens)
    com_ferramentas = _limitar(modelo.bind_tools(ferramentas), max_tokens) if ferramentas else sem_ferramentas
    prompt = prompt or (PROMPT_RAG if ferramentas else PROMPT_SISTEMA)

    def entrada(estado: Estado) -> dict:
        msg = estado["messages"][-1]
        if _humana_vazia(msg):
            return {"bloqueado": "mensagem vazia", "ferramentas": [], "skills": [], "truncada": False}
        texto = str(msg.content).lower()
        # Exceção: mensagens com histórico injetado ou pedido de resumo do chat
        if any(t in texto for t in _TRIGGERS_RESUMO) or "[histórico recente da conversa]" in texto:
            return {"bloqueado": "", "ferramentas": [], "skills": [], "truncada": False}
        from .skills import filtro_prompt
        bloqueio = filtro_prompt(str(msg.content))
        if bloqueio:
            return {"bloqueado": bloqueio, "ferramentas": [], "skills": ["filtro_prompt"], "truncada": False}
        return {"bloqueado": "", "ferramentas": [], "skills": [], "truncada": False}
    
    def responder(estado: Estado) -> dict:
        msgs = estado["messages"]
        n_consultas = consultas_no_turno(msgs)
        ultima_humana = str(
            msgs[-1].content if isinstance(msgs[-1], HumanMessage)
            else next((m.content for m in reversed(msgs) if isinstance(m, HumanMessage)), "")
        )
        eh_saudacao = any(s in ultima_humana.lower() for s in _SAUDACOES)
        eh_resumo_chat = any(t in ultima_humana.lower() for t in _TRIGGERS_RESUMO)
        usar = com_ferramentas if n_consultas < max_consultas else sem_ferramentas
        resposta = usar.invoke([SystemMessage(prompt)] + recentes(msgs, max_msgs))
        # Mínimo de 1 consulta se não for saudação, não for resumo de chat e não consultou ainda
        if (n_consultas == 0
                and not eh_saudacao
                and not eh_resumo_chat
                and not getattr(resposta, "tool_calls", None)):
            prompt_forcado = prompt + "\nATENÇÃO: você DEVE usar consultar_base agora antes de responder."
            resposta = com_ferramentas.invoke([SystemMessage(prompt_forcado)] + recentes(msgs, max_msgs))
        return {"messages": [resposta]}

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


def conversar(grafo, texto: str, thread_id: str,
              historico_json: list | None = None) -> tuple[str, dict]:
    cfg = {"configurable": {"thread_id": thread_id}}

    # Injeta sempre o histórico recente como contexto (últimas 10 mensagens)
    if historico_json and len(historico_json) > 1:
        historico = "\n".join(
            f"{'Usuário' if m['role'] == 'user' else 'Assistente'}: {m['texto'][:200]}"
            for m in historico_json[-10:]  # só as últimas 10
            if m.get("texto", "").strip()
        )
        texto = f"[HISTÓRICO RECENTE DA CONVERSA]\n{historico}\n\n[PERGUNTA ATUAL]\n{texto}"

    out = grafo.invoke({"messages": [HumanMessage(texto)]}, cfg)
    return str(out["messages"][-1].content), out