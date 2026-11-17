"""Gera data/gabarito/perguntas_proposto.jsonl com perguntas reescritas.

NAO altera perguntas.jsonl. As perguntas abaixo sao PROPOSTAS: so valem
depois da revisao humana (D-08). A pergunta antiga fica em `pergunta_original`.

Uso (na raiz do projeto):
    python scripts\\aplicar_reescrita.py
"""
import json
from pathlib import Path

ORIGEM = Path("data/gabarito/perguntas.jsonl")
SAIDA = Path("data/gabarito/perguntas_proposto.jsonl")

NOVAS = {
    "q01": "O impedimento de retorno ao serviço público previsto no art. 137 da Lei nº 8.112/90 alcança a pena de cassação de aposentadoria?",
    "q02": "Um servidor público federal pode exercer a advocacia por meio de sociedade unipessoal de advocacia?",
    "q03": "Qual regime disciplinar se aplica ao militar da reserva que exerce cargo em comissão de natureza civil?",
    "q04": "Os Termos de Ajustamento de Conduta (TAC) são públicos ou podem ter o acesso restringido?",
    "q05": "Quais providências a CGU, como órgão sancionador, deve adotar quando a pessoa jurídica paga a multa do PAR dentro do prazo?",
    "q06": "Em que consiste a sanção de publicação extraordinária da decisão condenatória no PAR?",
    "q07": "Como deve ser feita a citação de pessoa jurídica estrangeira que tem filial, agência ou sucursal no Brasil no PAR?",
    "q08": "O denunciante tem legitimidade para interpor recurso em processo administrativo disciplinar?",
    "q09": "Segundo a Nota Técnica nº 356/2022/CGUNE/CRG, quais requisitos devem ter os membros de comissão de PAD?",
    "q10": "A reincidência disciplinar pode ser reconhecida quando as irregularidades ocorrem em matrículas distintas do servidor?",
    "q11": "Em que fase do processo disciplinar pode ser instaurado o incidente de sanidade mental?",
    "q12": "O art. 14-A, §2º, do Código de Processo Penal, sobre defesa técnica, se aplica aos procedimentos disciplinares?",
    "q13": "Quais as consequências da extrapolação de prazos no processo disciplinar para a validade dos atos praticados?",
    "q14": "O servidor em licença para tratar de interesses particulares responde disciplinarmente por atividade particular exercida durante a licença?",
    "q15": "A concessão de aposentadoria pode ser indeferida enquanto o servidor cumpre um Termo de Ajustamento de Conduta (TAC)?",
    "q16": "É possível realizar busca e apreensão em domicílio no âmbito do processo administrativo disciplinar?",
    "q17": "É possível realizar oitivas de acusados, testemunhas e informantes por videoconferência, usando serviços de nuvem?",
    "q18": "A estabilidade do servidor é exigida para integrar comissão de processo administrativo disciplinar?",
    "q19": "É possível fracionar o cumprimento da penalidade de suspensão ou da multa que a substitui?",
    "q20": "Como funciona a investigação preliminar sumária (IPS) antes da instauração de um PAR?",
    "q21": "Quais são os requisitos para a desconsideração da personalidade jurídica por abuso de direito no PAR?",
    "q22": "Quais são as penalidades disciplinares expulsivas e quem tem competência para aplicá-las?",
    "q23": "Quais as implicações disciplinares da participação em licitação de empresa cujo sócio é parente de servidor da entidade licitante?",
    "q24": "A apuração disciplinar de ilícito contra a honra depende de queixa ou representação da vítima?",
    "q25": "Qual o efeito da incompetência da autoridade instauradora sobre a validade do processo disciplinar?",
    "q26": "O que a Lei nº 12.846/2013 considera administração pública estrangeira?",
    "q27": "Quais são os limites da apuração ética dos atos praticados por servidores de corregedorias?",
    "q28": "É necessário reduzir a termo os depoimentos gravados em audiência de processo disciplinar?",
    "q29": "O Ministro de Estado da CGU tem competência para aplicar sanção disciplinar?",
    "q30": "A gravação de conversa telefônica feita por um dos interlocutores, sem ciência do outro, é prova lícita no processo disciplinar?",
}


def main():
    itens = [
        json.loads(l)
        for l in ORIGEM.read_text(encoding="utf-8-sig").splitlines()
        if l.strip()
    ]
    ids = {i["id"] for i in itens}
    if ids != set(NOVAS):
        raise SystemExit(f"ids diferentes: faltam {sorted(set(NOVAS) - ids)}, sobram {sorted(ids - set(NOVAS))}")

    saida = []
    for it in itens:
        novo = dict(it)
        novo["pergunta_original"] = it["pergunta"]
        novo["pergunta"] = NOVAS[it["id"]]
        novo["origem"] = "sintetico_reescrito"
        saida.append(novo)

    texto = "\n".join(json.dumps(i, ensure_ascii=False) for i in saida) + "\n"
    SAIDA.write_text(texto, encoding="utf-8", newline="\n")
    print(f"OK: {len(saida)} perguntas propostas em {SAIDA}")
    print(f"maior pergunta: {max(len(v) for v in NOVAS.values())} caracteres")


if __name__ == "__main__":
    main()
