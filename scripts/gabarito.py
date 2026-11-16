"""Revisao humana do gabarito (D-08, D-11).

Uso (na raiz do projeto):
  python scripts/gabarito.py revisar    # revisa as perguntas pendentes, uma por vez
  python scripts/gabarito.py status     # mostra o andamento
  python scripts/gabarito.py exportar   # grava as aprovadas em data/gabarito/perguntas.jsonl
  python scripts/gabarito.py validar    # aponta perguntas suspeitas de nao serem perguntas bem formadas
  python scripts/gabarito.py rever q14 q30   # reabre essas perguntas para corrigir (depois: revisar)
O progresso e salvo a cada resposta; pode sair (s) e continuar depois.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cgu_rag import config  # noqa: E402,F401
from cgu_rag import gabarito as gb  # noqa: E402

RASCUNHO = Path("data/gabarito/rascunho.jsonl")
FINAL = Path("data/gabarito/perguntas.jsonl")
MINIMO = 30


def abrir_db():
    try:
        from cgu_rag.legado import rag_cgu_pipeline as legado
        return legado.connect()
    except Exception as e:
        print("(sem acesso ao banco; o trecho nao sera exibido):", e)
        return None


def trecho(con, it, n=700) -> str:
    if con is None:
        return ""
    r = con.execute(
        "SELECT c.texto FROM chunks c JOIN documents d ON d.id = c.doc_id "
        "WHERE d.titulo = ? AND c.titulo = ? AND c.pag_ini = ? LIMIT 1",
        (it.get("doc"), it.get("esperado"), it.get("pag_ini"))).fetchone()
    return " ".join((r[0] if r else "").split())[:n]


def pedir_fase():
    while True:
        s = input("Fase(s): [1] admissibilidade [2] acusatoria [3] julgamento (combine: 13, 123=todas) | [4] PAR | [0] fora do fluxo | Enter = voltar > ")
        try:
            return gb.interpretar_fase(s)
        except ValueError as e:
            print(e)


def mostrar_resumo(itens):
    r = gb.resumo(itens)
    print(f"\ntotal {r['total']} | aprovadas {r['aprovado']} | descartadas {r['descartado']} | pendentes {r['pendente']}")
    print("aprovadas por fase do PAD (conta em cada fase marcada):", r["por_fase"])
    print(f"transversais (as 3 fases): {r['transversais']} | PAR: {r['par']} | fora do fluxo: {r['fora_do_fluxo']}")


def revisar():
    if not RASCUNHO.exists():
        raise SystemExit(f"ERRO: {RASCUNHO} nao encontrado.")
    itens = gb.preparar(gb.carregar(RASCUNHO))
    gb.salvar(RASCUNHO, itens)
    fila = gb.pendentes(itens)
    if not fila:
        print("Nenhuma pergunta pendente.")
        return mostrar_resumo(itens)
    con = abrir_db()
    try:
        for n, it in enumerate(fila, 1):
            print(f"\n[{n}/{len(fila)}] {it['id']}")
            print("Pergunta :", it["pergunta"])
            print("Esperado :", f"{str(it.get('doc'))[:60]} | {str(it.get('esperado'))[:70]} | pags {it.get('pag_ini')}-{it.get('pag_fim')}")
            t = trecho(con, it)
            if t:
                print("Trecho   :", t)
            a = ""
            while a not in ("a", "e", "d", "p", "s"):
                a = input("[a]provar  [e]ditar  [d]escartar  [p]ular  [s]air > ").strip().lower()
            if a == "s":
                break
            if a == "p":
                continue
            if a == "d":
                gb.aplicar(it, "descartar")
            else:
                nova = None
                if a == "e":
                    nova = input("Nova pergunta: ").strip()
                    if not nova:
                        print("vazia; item pulado")
                        continue
                fase = pedir_fase()
                if fase is None:
                    print("item pulado")
                    continue
                gb.aplicar(it, "editar" if a == "e" else "aprovar", fase=fase, pergunta=nova)
            gb.salvar(RASCUNHO, itens)
    except (EOFError, KeyboardInterrupt):
        print("\ninterrompido; o progresso ja esta salvo.")
    mostrar_resumo(itens)


def status():
    mostrar_resumo(gb.preparar(gb.carregar(RASCUNHO)))


def exportar():
    aprovadas = gb.exportar(gb.carregar(RASCUNHO))
    if not aprovadas:
        raise SystemExit("Nenhuma pergunta aprovada; nada foi gravado.")
    gb.salvar(FINAL, aprovadas)
    print(f"{len(aprovadas)} perguntas gravadas em {FINAL}")
    if len(aprovadas) < MINIMO:
        print(f"AVISO: meta minima e {MINIMO} aprovadas.")


def validar():
    itens = gb.preparar(gb.carregar(RASCUNHO))
    achadas = [(it, gb.suspeitas(it["pergunta"])) for it in itens if it.get("status") != "descartado"]
    achadas = [(it, s) for it, s in achadas if s]
    print(f"{len(achadas)} pergunta(s) suspeita(s) de {len(itens)}")
    for it, s in achadas:
        print(f"\n{it['id']} [{it.get('status')}] ({'; '.join(s)})\n  {it['pergunta'][:300]}")
    if achadas:
        print("\nPara corrigir: python scripts/gabarito.py rever " + " ".join(it["id"] for it, _ in achadas) + "   (depois: revisar)")


def rever(ids):
    if not ids:
        raise SystemExit("Informe os ids. Ex.: python scripts/gabarito.py rever q14 q30")
    itens = gb.preparar(gb.carregar(RASCUNHO))
    reabertos = gb.reabrir(itens, ids)
    gb.salvar(RASCUNHO, itens)
    ausentes = sorted(set(ids) - set(reabertos))
    print(f"{len(reabertos)} pergunta(s) reaberta(s): {' '.join(reabertos)}")
    if ausentes:
        print("ids nao encontrados:", " ".join(ausentes))
    print("Agora rode: python scripts/gabarito.py revisar   (use [e]ditar para reescrever a pergunta)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Revisao humana do gabarito")
    ap.add_argument("comando", choices=["revisar", "status", "exportar", "validar", "rever"])
    ap.add_argument("ids", nargs="*", help="ids para o comando rever (ex.: q14 q30)")
    a = ap.parse_args()
    if a.comando == "rever":
        rever(a.ids)
    else:
        {"revisar": revisar, "status": status, "exportar": exportar, "validar": validar}[a.comando]()
