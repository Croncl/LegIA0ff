"""Gera data/gabarito/perguntas_proposto.jsonl com perguntas reescritas (v2, curtas).

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
    "q01": "O art. 137 da Lei 8.112/90 (impedimento de retorno) se aplica à cassação de aposentadoria?",
    "q02": "O servidor público federal pode exercer a advocacia por sociedade unipessoal?",
    "q03": "Qual regime disciplinar se aplica ao militar da reserva em cargo em comissão civil?",
    "q04": "O TAC (Termo de Ajustamento de Conduta) é público ou pode ter acesso restrito?",
    "q05": "Quais providências a CGU adota se a pessoa jurídica paga a multa do PAR no prazo?",
    "q06": "O que é a publicação extraordinária no PAR?",
    "q07": "Como se cita pessoa jurídica estrangeira com filial, agência ou sucursal no Brasil, no PAR?",
    "q08": "O denunciante tem legitimidade para recorrer em processo disciplinar?",
    "q09": "Quais requisitos devem ter os membros de comissão de PAD (NT 356/2022)?",
    "q10": "Há reincidência quando as irregularidades ocorrem em matrículas distintas do servidor?",
    "q11": "Em que fase do processo disciplinar pode ser instaurado o incidente de sanidade mental?",
    "q12": "O art. 14-A, §2º, do CPP (defesa técnica) se aplica aos procedimentos disciplinares?",
    "q13": "A extrapolação de prazos no processo disciplinar invalida os atos praticados?",
    "q14": "O servidor em licença para interesses particulares responde por atividade privada nesse período?",
    "q15": "Servidor que cumpre TAC pode se aposentar?",
    "q16": "Cabe busca e apreensão em domicílio no processo administrativo disciplinar?",
    "q17": "Oitivas de acusados e testemunhas podem ser feitas por videoconferência em serviços de nuvem?",
    "q18": "A estabilidade é necessária aos membros da comissão de PAD?",
    "q19": "É possível fracionar o cumprimento da suspensão ou da multa disciplinar?",
    "q20": "O que é a investigação preliminar sumária (IPS) no PAR?",
    "q21": "Quais os requisitos para desconsiderar a personalidade jurídica por abuso de direito no PAR?",
    "q22": "Quais são as penalidades disciplinares expulsivas e quem pode aplicá-las?",
    "q23": "Quais as implicações disciplinares de licitante cujo sócio é parente de servidor da entidade?",
    "q24": "A apuração disciplinar de ilícito contra a honra depende de representação da vítima?",
    "q25": "Qual o efeito da incompetência da autoridade instauradora na validade do processo disciplinar?",
    "q26": "O que é administração pública estrangeira na Lei 12.846/2013?",
    "q27": "Quais os limites da apuração ética de atos de servidores de corregedorias?",
    "q28": "Depoimentos gravados no processo disciplinar precisam ser reduzidos a termo?",
    "q29": "O Ministro da CGU pode aplicar sanção disciplinar?",
    "q30": "A gravação de telefonema por um interlocutor, sem ciência do outro, é prova lícita no PAD?",
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
