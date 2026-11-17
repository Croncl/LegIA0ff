"""Medicao robusta do agente (RAG agentico) para UM modelo (plano da D-17, fases 1 e 3).

Uso (na raiz do projeto, com o Ollama rodando e o computador sem outro uso pesado):
  python scripts/medir_agente.py --modelo hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M --pensar false
  python scripts/medir_agente.py --modelo qwen2.5:7b
  python scripts/medir_agente.py --modelo SparkLLM/Spark-X2.6-4B:q8_0 --n 30

O que faz: confere que o modelo esta instalado; aquece o modelo (uma pergunta fora da medicao);
roda as N perguntas normativas do gabarito e 6 de controle (4 conversas simples que NAO devem consultar a
base e 2 fora de escopo); guarda as respostas completas; conta erros; calcula a mediana; aplica os
criterios da D-17 (src/cgu_rag/criterios.py). Cada pergunta usa uma conversa nova.
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag import metricas as mt  # noqa: E402
from cgu_rag.agente.ferramentas import criar_buscador, criar_ferramenta_consulta  # noqa: E402
from cgu_rag.agente.grafo import conversar, criar_grafo  # noqa: E402
from cgu_rag.agente.modelo import criar_modelo  # noqa: E402
from cgu_rag.config import settings  # noqa: E402
from cgu_rag.criterios import CRITERIOS, avaliar_criterios, mediana  # noqa: E402

CITA_PAGINA = re.compile(r"p[aá]gs?\.?\s*\d", re.I)
CONTROLES = [
    ("conversa", "Oi, tudo bem?"),
    ("conversa", "Obrigado pela ajuda!"),
    ("conversa", "Bom dia! Pode se apresentar em uma frase?"),
    ("conversa", "Entendi, muito obrigado."),
    ("fora_de_escopo", "Qual e a capital da Franca?"),
    ("fora_de_escopo", "Me de uma receita de bolo de cenoura."),
]
AQUECIMENTO = "Qual e o prazo de prescricao no processo disciplinar?"


def media(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def verificar_ollama(modelo: str) -> dict:
    base = settings.llm_base_url.rsplit("/v1", 1)[0]
    try:
        tags = requests.get(base + "/api/tags", timeout=10).json()["models"]
        versao = requests.get(base + "/api/version", timeout=10).json().get("version")
    except Exception as e:
        raise SystemExit(f"ERRO: nao consegui falar com o Ollama em {base}: {e}")
    achado = next((t for t in tags if t["name"] in (modelo, modelo + ":latest")), None)
    if not achado:
        raise SystemExit(f"ERRO: o modelo '{modelo}' nao esta instalado. Confira o nome em 'ollama list'.")
    det = achado.get("details", {})
    return {"digest": str(achado.get("digest", ""))[:12], "ollama": versao,
            "quantizacao": det.get("quantization_level"), "parametros": det.get("parameter_size")}


def commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "?"


def fonte(r) -> str:
    return f"{r['nota_tecnica'] or r['doc_titulo']} | {r['titulo']} | pags {r['pag_ini']}-{r['pag_fim']}"


def turno(grafo, log, texto: str, thread: str) -> dict:
    log.clear()
    t0 = time.time()
    erro, resposta, chamadas = "", "", []
    try:
        resposta, estado = conversar(grafo, texto, thread)
        chamadas = estado.get("ferramentas", [])
    except Exception as e:  # nao interrompe a medicao; o erro e contado
        erro = f"{type(e).__name__}: {str(e)[:300]}"
    linhas = [r for lote in log for r in lote]
    return {"pergunta": texto, "resposta": resposta, "erro": erro,
            "consultas": [c["args"].get("consulta") for c in chamadas],
            "fontes": [fonte(r) for r in linhas], "linhas": linhas,
            "citou_pagina": bool(CITA_PAGINA.search(resposta)), "segundos": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--n", type=int, default=30, help="perguntas normativas do gabarito (padrao: todas as 30)")
    ap.add_argument("--pensar", choices=["padrao", "true", "false"], default="padrao",
                    help="false desliga o raciocinio (thinking) do modelo")
    ap.add_argument("--k", type=int, default=4, help="trechos devolvidos por consulta (fase 5 testa 8)")
    ap.add_argument("--gabarito", default="data/gabarito/perguntas.jsonl")
    a = ap.parse_args()

    info = verificar_ollama(a.modelo)
    os.environ.pop("LLM_PENSAR", None)  # a opcao --pensar manda; a variavel de ambiente nao interfere
    itens = [json.loads(l) for l in Path(a.gabarito).read_text(encoding="utf-8").splitlines() if l.strip()]
    itens = random.Random(42).sample(itens, min(a.n, len(itens)))
    modelo = criar_modelo(model=a.modelo, pensar=False if a.pensar == "false" else None)

    base, log = criar_buscador(), []

    def buscador(q, k):
        linhas = base(q, k)
        log.append(linhas)
        return linhas

    grafo = criar_grafo(modelo, ferramentas=[criar_ferramenta_consulta(buscador, k=a.k)])
    print(f"modelo={a.modelo} digest={info['digest']} quant={info['quantizacao']} ollama={info['ollama']} pensar={a.pensar} k={a.k}")
    print("aquecendo o modelo (fora da medicao)...")
    aq = turno(grafo, log, AQUECIMENTO, "aquecimento")
    print(f"aquecimento: {aq['segundos']} s" + (f" ERRO: {aq['erro']}" if aq["erro"] else ""))

    detalhes = []
    for i, it in enumerate(itens, 1):
        d = turno(grafo, log, it["pergunta"], f"n{i}")
        d.update({"tipo": "normativa", "id": it["id"], "fase": it.get("fase"), "esperado": it["esperado"],
                  "posicao_do_acerto": mt.posicao(it, d["linhas"]) if d["linhas"] else None})
        detalhes.append(d)
        print(f"[{i}/{len(itens)}] consultas={len(d['consultas'])} acerto={'sim' if d['posicao_do_acerto'] else 'nao'} "
              f"{d['segundos']} s" + (" ERRO" if d["erro"] else ""))
        if i == 3 and all(x["erro"] for x in detalhes):
            raise SystemExit("ERRO: as 3 primeiras perguntas falharam; interrompido. Primeiro erro: " + detalhes[0]["erro"])
    for j, (tipo, pergunta) in enumerate(CONTROLES, 1):
        d = turno(grafo, log, pergunta, f"c{j}")
        d.update({"tipo": tipo, "id": f"c{j}", "fase": None, "esperado": None, "posicao_do_acerto": None})
        detalhes.append(d)
        print(f"[controle {j}/{len(CONTROLES)}] {tipo}: consultas={len(d['consultas'])} {d['segundos']} s")

    norm = [d for d in detalhes if d["tipo"] == "normativa"]
    conv = [d for d in detalhes if d["tipo"] == "conversa"]
    fora = [d for d in detalhes if d["tipo"] == "fora_de_escopo"]
    m = {
        "n": len(norm), "consultou": media([bool(d["consultas"]) for d in norm]),
        "acerto_na_consulta": media([d["posicao_do_acerto"] is not None for d in norm]),
        "consultas_medias": media([len(d["consultas"]) for d in norm]),
        "controles_consultados": sum(bool(d["consultas"]) for d in conv),
        "fora_de_escopo_consultou": sum(bool(d["consultas"]) for d in fora),
        "citou_sem_consultar": media([d["citou_pagina"] and not d["consultas"] for d in detalhes]),
        "recusa_indevida": sum(d["resposta"].strip().startswith("Esta pergunta") for d in norm),
        "erros": sum(bool(d["erro"]) for d in detalhes),
        "mediana_s": round(mediana([d["segundos"] for d in norm]), 1), "media_s": media([d["segundos"] for d in norm]),
        "mediana_controle_s": round(mediana([d["segundos"] for d in conv]), 1),
        "aquecimento_s": aq["segundos"], "modelo": a.modelo, "pensar": a.pensar, "k": a.k,
        "digest": info["digest"], "quantizacao": info["quantizacao"], "parametros": info["parametros"],
        "ollama": info["ollama"], "contexto": os.getenv("OLLAMA_CONTEXT_LENGTH", "padrao do Ollama"),
        "commit": commit(), "temperatura": 0.1,
    }
    aprovado, motivos = avaliar_criterios(m)
    m["aprovado_criterios_d17"] = aprovado
    m["motivos_reprovacao"] = motivos
    rotulo = f"pensar={a.pensar}" + (f", k={a.k}" if a.k != 4 else "")
    nome = f"Agente {a.modelo} [{rotulo}] n={m['n']}"
    mt.registrar("agente", nome, m)
    slug = re.sub(r"[^A-Za-z0-9.]+", "_", f"{a.modelo}_{rotulo}")
    saida = Path("results") / f"agente_{slug}.jsonl"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text("\n".join(json.dumps({k: v for k, v in d.items() if k != "linhas"}, ensure_ascii=False)
                               for d in detalhes), encoding="utf-8")
    print("\n" + json.dumps(m, indent=1))
    print("\nVEREDITO (criterios da D-17, confirmados em 16/11/2026):", "APROVADO" if aprovado else "REPROVADO")
    for x in motivos:
        print(" -", x)
    print("detalhes (respostas completas) em", saida, "| limites:", CRITERIOS)


if __name__ == "__main__":
    main()
