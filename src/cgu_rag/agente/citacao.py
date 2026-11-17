"""Citacao curta de fontes montada pelo SISTEMA, nao pelo modelo (D-18).

O modelo responde em ate 3 frases, sem citar fonte. Depois, o no `saida` do grafo anexa
"Fonte: <documento curto>, pag. X" a partir dos trechos que a ferramenta recuperou no turno.
Assim o modelo nao consegue inventar pagina, e a citacao e curta.
"""
from __future__ import annotations

import re

MAX_FONTES = 2           # fontes anexadas a uma resposta
MIN_SOBREPOSICAO = 3     # palavras em comum (>= 5 letras) para considerar que o trecho sustenta a resposta
RAZAO_SEGUNDA = 0.6      # a 2a fonte so entra se tiver >= 60% da sobreposicao da melhor

_PALAVRA = re.compile(r"[a-záéíóúâêôãõç]{5,}")
_NAO_ENCONTREI = re.compile(r"n[aã]o encontrei")
_CITACAO_COLCHETES = re.compile(r"\s*\[[^\]\n]*p[áa]gs?\.?[^\]\n]*\]", re.IGNORECASE)
_LINHA_FONTE = re.compile(r"(?im)^\s*fontes?\s*:.*$")


def nome_curto(titulo: str | None, nota_tecnica: str | None = None) -> str:
    """'EMENTARIO DE NOTAS TECNICAS ... (3a edicao) (2026)' -> 'Ementário 3ª ed.' (+ NT, se houver)."""
    t = (titulo or "").strip()
    up = t.upper()
    m = re.search(r"\((\d+)\s*ª\s*edi", t, re.IGNORECASE)
    ed = f" {m.group(1)}ª ed." if m else ""
    if "EMENT" in up:
        nome = f"Ementário{ed}"
    elif "RESPONSABILIZA" in up:
        nome = f"Manual PAR{ed}"
    elif "PROCESSO ADMINISTRATIVO DISCIPLINAR" in up:
        nome = f"Manual PAD{ed}"
    else:
        nome = re.sub(r"\s+", " ", t)[:40] or "documento"
    nt = re.search(r"(\d+/\d{4})", nota_tecnica or "")
    if nt and nome.startswith("Ementário"):
        nome += f" (NT {nt.group(1)})"
    return nome


def _paginas(ini, fim) -> str:
    if ini is None:
        return ""
    return f"pág. {ini}" if fim in (None, ini) else f"págs {ini}-{fim}"


def _palavras(texto: str | None) -> set[str]:
    return set(_PALAVRA.findall((texto or "").lower()))


def escolher_fontes(resposta: str, trechos: list[dict], maximo: int = MAX_FONTES) -> list[dict]:
    """Escolhe, entre os trechos recuperados no turno, os que mais se sobrepoem a resposta.

    `trechos` vem na ordem de relevancia (consulta mais recente primeiro). Sem sobreposicao minima,
    cai no primeiro trecho (o mais relevante da ultima consulta)."""
    if not trechos:
        return []
    alvo = _palavras(resposta)
    pont = sorted(
        ((len(alvo & _palavras(t.get("texto"))), -i, t) for i, t in enumerate(trechos)),
        key=lambda x: (x[0], x[1]),
        reverse=True,
    )
    melhor = pont[0][0]
    if melhor < MIN_SOBREPOSICAO:
        return [trechos[0]]
    escolhidos, vistos = [], set()
    for score, _, t in pont:
        if score < max(MIN_SOBREPOSICAO, RAZAO_SEGUNDA * melhor):
            break
        chave = (t.get("doc"), t.get("pag_ini"), t.get("pag_fim"))
        if chave in vistos:
            continue
        vistos.add(chave)
        escolhidos.append(t)
        if len(escolhidos) == maximo:
            break
    return escolhidos


def _faixas_por_documento(escolhidos: list[dict]) -> dict[str, list[list[int]]]:
    """Agrupa por documento e junta faixas de paginas que se sobrepoem ou se tocam (114 e 114-115 -> 114-115)."""
    por_doc: dict[str, list[list[int]]] = {}
    for t in escolhidos:
        doc = str(t.get("doc") or "documento")
        faixas = por_doc.setdefault(doc, [])
        ini, fim = t.get("pag_ini"), t.get("pag_fim")
        if ini is None:
            continue
        fim = ini if fim is None else fim
        faixas.append([ini, fim])
    for doc, faixas in por_doc.items():
        mescladas: list[list[int]] = []
        for ini, fim in sorted(faixas):
            if mescladas and ini <= mescladas[-1][1] + 1:
                mescladas[-1][1] = max(mescladas[-1][1], fim)
            else:
                mescladas.append([ini, fim])
        por_doc[doc] = mescladas
    return por_doc


def montar_fonte(escolhidos: list[dict]) -> str:
    itens = []
    for doc, faixas in _faixas_por_documento(escolhidos).items():
        paginas = ", ".join(_paginas(ini, fim) for ini, fim in faixas)
        itens.append(f"{doc}, {paginas}" if paginas else doc)
    return "Fonte: " + "; ".join(itens)


def limpar_citacao_do_modelo(texto: str) -> str:
    """Remove '[doc, págs X-Y]' e linhas 'Fonte: ...' que o modelo tenha escrito por conta propria."""
    texto = _CITACAO_COLCHETES.sub("", texto)
    texto = _LINHA_FONTE.sub("", texto)
    return texto.strip()


def anexar_fonte(resposta: str, trechos: list[dict]) -> str:
    """Devolve a resposta com a fonte anexada.

    Sem trechos (nao houve consulta) ou com 'Não encontrei', devolve a resposta INTACTA: assim uma pagina
    que o modelo cite sem ter consultado continua visivel para a metrica `citou_sem_consultar`."""
    if not trechos or _NAO_ENCONTREI.search(resposta.lower()):
        return resposta
    limpo = limpar_citacao_do_modelo(resposta) or resposta
    return f"{limpo}\n\n{montar_fonte(escolher_fontes(limpo, trechos))}"
