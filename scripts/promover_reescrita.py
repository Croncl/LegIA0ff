"""Promove as perguntas reescritas (aprovadas pelo autor em 17/11/2026) ao gabarito.

O fluxo do gabarito e: rascunho.jsonl (com status) -> `gabarito.py exportar` -> perguntas.jsonl.
Por isso a troca e feita no RASCUNHO; depois voce roda `validar` e `exportar`.

- Le data/gabarito/perguntas_proposto.jsonl (gerado por aplicar_reescrita.py e revisado).
- Faz copia de seguranca dos arquivos antigos (so se a copia ainda nao existir).
- Troca o campo `pergunta` no rascunho e guarda o texto antigo em `pergunta_original`.
- Pode ser rodado de novo sem perder o original.

Uso (na raiz do projeto):  python scripts\\promover_reescrita.py
"""
import json
import shutil
from pathlib import Path

G = Path("data/gabarito")
PROPOSTO = G / "perguntas_proposto.jsonl"
RASCUNHO = G / "rascunho.jsonl"
OFICIAL = G / "perguntas.jsonl"


def ler(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def main():
    novos = {i["id"]: i["pergunta"] for i in ler(PROPOSTO)}
    itens = ler(RASCUNHO)
    ids = {i["id"] for i in itens}
    if ids != set(novos):
        raise SystemExit(f"ids diferentes: faltam {sorted(set(novos) - ids)}, sobram {sorted(ids - set(novos))}")

    for origem, copia in ((RASCUNHO, G / "rascunho_antigo_enunciados.jsonl"),
                          (OFICIAL, G / "perguntas_antigo_enunciados.jsonl")):
        if origem.exists() and not copia.exists():
            shutil.copy2(origem, copia)
            print(f"copia de seguranca: {copia}")

    for it in itens:
        it.setdefault("pergunta_original", it["pergunta"])
        it["pergunta"] = novos[it["id"]]

    texto = "\n".join(json.dumps(i, ensure_ascii=False) for i in itens) + "\n"
    RASCUNHO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"OK: {len(itens)} perguntas trocadas em {RASCUNHO}")
    print("Proximo: python scripts\\gabarito.py validar   e depois   python scripts\\gabarito.py exportar")


if __name__ == "__main__":
    main()
