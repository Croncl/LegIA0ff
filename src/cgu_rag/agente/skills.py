"""
Skills do agente (R10).

Skill A — resumir_trecho: resume um trecho normativo em até 3 bullet points.
Skill C — filtro_prompt: guardrail de entrada que bloqueia prompts longos
           contando apenas palavras relevantes (sem stopwords), com respostas
           bem-humoradas.

Uso no grafo:
  from cgu_rag.agente.skills import filtro_prompt, resumir_trecho
  # filtro_prompt: chamar ANTES de passar ao grafo
  # resumir_trecho: ferramenta disponível ao agente
"""
from __future__ import annotations

import random
import re

from langchain_core.tools import tool

# ══════════════════════════════════════════════════════════════
# SKILL A — Resumo de trecho normativo
# ══════════════════════════════════════════════════════════════

@tool
def resumir_trecho(texto: str) -> str:
    """Resume um trecho de normativo ou manual da CGU em até 3 bullet points objetivos.
    Use quando o usuário pedir um resumo ou quando o trecho recuperado for muito longo.

    Args:
        texto: Trecho do normativo a resumir (até 2000 caracteres).
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

    try:
        from cgu_rag.agente.modelo import criar_modelo
        from cgu_rag.config import settings

        modelo = criar_modelo()
        prompt = (
            "Resuma o trecho abaixo em até 3 bullet points curtos e objetivos. "
            "Cada bullet deve ter no máximo 20 palavras. "
            "Responda SOMENTE com os bullets, sem introdução.\n\n"
            f"TRECHO:\n{texto[:2000]}"
        )
        resposta = modelo.invoke(prompt)
        # LangChain retorna AIMessage ou str dependendo do modelo
        if hasattr(resposta, "content"):
            return resposta.content.strip()
        return str(resposta).strip()
    except Exception as e:
        return f"Erro ao resumir: {e}"


# ══════════════════════════════════════════════════════════════
# SKILL C — Filtro de prompt (guardrail de entrada)
# ══════════════════════════════════════════════════════════════

# Stopwords mais comuns em português
_STOPWORDS_PT = {
    # -------------------------------------------------------------------
    # 1. Conectivos e Pronomes Gerais 
    # -------------------------------------------------------------------
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "pelo", "pela", "pelos", "pelas", "para", "pra", "com", "sem",
    "e", "ou", "mas", "pois", "que", "se", "como", "quando", "onde",
    "eu", "tu", "ele", "ela", "nós", "vós", "eles", "elas",
    "me", "te", "se", "nos", "vos", "lhe", "lhes", "meu", "minha", "seu", "sua",
    "isso", "isto", "aquilo", "esse", "essa", "este", "esta", "muito", "mais",
    "algum", "alguma", "alguns", "algumas", "todo", "toda", "todos", "todas",
    "outro", "outra", "outros", "outras", "qual", "quais", "quanto", "quanta",

    # -------------------------------------------------------------------
    # 2. Fórmulas de Praxe e "Burocracia" (Aparecem em todo documento)
    # -------------------------------------------------------------------
    "senhor", "senhora", "senhores", "senhoras", "ilustríssimo", "ilustre", 
    "excelentíssimo", "excelentíssima", "prezado", "prezada", 
    "atenciosamente", "respeitosamente", "cordialmente", "conforme", 
    "consoante", "segundo", "destarte", "portanto", "outrossim", "ademais", 
    "contudo", "entretanto", "todavia", "porém", "embora", "posto", 
    "visto", "uma", "vez", "dessa", "desse", "disso", "nisso", "nesse", 
    "nesta", "neste", "daquele", "daquela", "àquele", "àquela",

    # -------------------------------------------------------------------
    # 3. Referências Genéricas (O RAG já filtra pelo contexto)
    # -------------------------------------------------------------------
    "artigo", "art", "inciso", "parágrafo", "alínea", "item", "anexo", 
    "página", "folha", "fls", "doc", "pdf", "referente", "referido", 
    "supracitado", "mencionado", "citado", "acima", "abaixo", "seguinte", 
    "anterior", "respectivo", "correspondente", "presente", "atual", 
    "atualmente", "agora", "então", "após", "antes", "durante", "mediante", 
    "através", "junto", "juntamente", "bem", "também", "ainda", "já",

    # -------------------------------------------------------------------
    # 4. Verbos de Ligação e Relato (Comuns em despachos e relatórios)
    # -------------------------------------------------------------------
    "é", "são", "foi", "eram", "ser", "está", "estão", "ter", "tem", "tinha",
    "consta", "constam", "trata", "tratam", "refere", "referem", "versa", 
    "versam", "informa", "informam", "relata", "relatam", "descreve", 
    "descrevem", "solicita", "solicitam", "requer", "requerem", "encaminha", 
    "encaminham", "sendo", "sido", "havia", "houve", "houver", "havendo",
    
    # -------------------------------------------------------------------
    # 5. Palavras Genéricas de Tempo/Modo (CUIDADO: não incluir 'data', 'dia', 'prazo')
    # -------------------------------------------------------------------
    "mês", "meses", "ano", "anos", "horas", "forma", "formas", "modo", 
    "maneira", "caso", "casos", "situação", "situações", "parte", "partes", 
    "coisa", "coisas", "fato", "fatos", "vez", "vezes", "local", "locais",
    "geral", "gerais", "específico", "específica", "determinado", "determinada",

    # -------------------------------------------------------------------
    # 6. Números por extenso e numerais romanos comuns
    # -------------------------------------------------------------------
    "um", "dois", "duas", "três", "quatro", "cinco", "seis", "sete", "oito", 
    "nove", "dez", "vinte", "trinta", "cem", "mil", "i", "ii", "iii", "iv", 
    "v", "vi", "vii", "viii", "ix", "x",
}

_RESPOSTAS_LONGAS = [
    "Erro 404: Paciência não encontrada. Seja objetivo e resuma em 20 palavras ou menos!",
    "Vai com calma, meu nobre, que esse seu PC da Xuxa não tanka.",
    "You shall not pass! (Até porque essa GPU tá fritando um ovo neste exato momento).",
    "Mestre dos Magos: procure a resposta está dentro de você...(sua CPU já pediu arrego).",
    "Quem tem teto de vidro e processador Celeron não atira pedra no cluster dos outros.",
    "Muito cavalo para pouco pasto e muita marra para pouca RAM livre!",
    "Se achando o dono da cocada preta, mas o ventilador do gabinete parece uma turbina de Boeing.",
    "Vixe! Com esse tamanho de prompt, até o disquete de 3 polegadas andava mais rápido.",
]


def filtro_prompt(prompt_usuario: str, limite: int = 20) -> str | None:
    """Guardrail de entrada (R11): bloqueia prompts com mais de `limite` palavras relevantes.

    Conta apenas palavras que não são stopwords. Se o prompt passar no filtro,
    retorna None (siga normalmente). Se reprovar, retorna uma mensagem bem-humorada.

    Args:
        prompt_usuario: Texto digitado pelo usuário.
        limite: Máximo de palavras relevantes permitidas (padrão 20).

    Returns:
        None se o prompt for aceito; str com mensagem de bloqueio se for longo demais.
    """
    palavras = re.findall(r'\b\w+\b', prompt_usuario.lower())
    palavras_uteis = [p for p in palavras if p not in _STOPWORDS_PT]

    if len(palavras_uteis) > limite:
        return random.choice(_RESPOSTAS_LONGAS)

    return None
