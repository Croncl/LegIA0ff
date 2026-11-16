"""Criterios de decisao do modelo do agente (D-17). PROPOSTA ate a confirmacao do autor.

Ajuste os limites aqui e todos os scripts passam a usar os novos valores.
"""
from __future__ import annotations

CRITERIOS = {
    "consulta_min": 0.90,           # fracao das perguntas normativas em que o agente consultou a base
    "controles_max": 1,             # no maximo N das 4 conversas simples podem acionar a consulta
    "citou_sem_consultar_max": 0.0,  # fracao de respostas com pagina citada sem ter consultado
    "erros_max": 1,                 # erros (excecoes) por rodada
    "mediana_s_max": 60.0,          # mediana de segundos por pergunta normativa
}


def mediana(xs: list[float]) -> float:
    s = sorted(xs)
    if not s:
        return 0.0
    meio = len(s) // 2
    return float(s[meio]) if len(s) % 2 else (s[meio - 1] + s[meio]) / 2


def avaliar_criterios(m: dict, c: dict | None = None) -> tuple[bool, list[str]]:
    """Devolve (aprovado, motivos_da_reprovacao)."""
    c = c or CRITERIOS
    falhas = []
    if m["consultou"] < c["consulta_min"]:
        falhas.append(f"consultou {m['consultou']:.0%} (minimo {c['consulta_min']:.0%})")
    if m["controles_consultados"] > c["controles_max"]:
        falhas.append(f"{m['controles_consultados']} conversas simples acionaram a consulta (maximo {c['controles_max']})")
    if m["citou_sem_consultar"] > c["citou_sem_consultar_max"]:
        falhas.append(f"citou pagina sem consultar em {m['citou_sem_consultar']:.0%} das respostas (maximo {c['citou_sem_consultar_max']:.0%})")
    if m["erros"] > c["erros_max"]:
        falhas.append(f"{m['erros']} erros (maximo {c['erros_max']})")
    if m["mediana_s"] > c["mediana_s_max"]:
        falhas.append(f"mediana {m['mediana_s']:.0f} s (maximo {c['mediana_s_max']:.0f} s)")
    return not falhas, falhas
