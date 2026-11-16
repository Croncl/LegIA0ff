from cgu_rag.criterios import avaliar_criterios, mediana

BOM = {"consultou": 0.95, "controles_consultados": 0, "citou_sem_consultar": 0.0, "erros": 0, "mediana_s": 20.0}


def test_mediana():
    assert mediana([]) == 0.0 and mediana([3]) == 3 and mediana([1, 9, 2]) == 2 and mediana([1, 2, 3, 10]) == 2.5


def test_aprovado():
    assert avaliar_criterios(BOM) == (True, [])


def test_cada_criterio_reprova_sozinho():
    for campo, ruim in (("consultou", 0.8), ("controles_consultados", 2), ("citou_sem_consultar", 0.03),
                        ("erros", 2), ("mediana_s", 61.0)):
        ok, motivos = avaliar_criterios({**BOM, campo: ruim})
        assert not ok and len(motivos) == 1, campo


def test_limites_exatos_passam():
    ok, _ = avaliar_criterios({**BOM, "consultou": 0.90, "controles_consultados": 1, "erros": 1, "mediana_s": 60.0})
    assert ok
