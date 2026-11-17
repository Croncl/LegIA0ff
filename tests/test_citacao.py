from cgu_rag.agente.citacao import anexar_fonte, escolher_fontes, limpar_citacao_do_modelo, nome_curto

TRECHOS = [
    {"doc": "Manual PAD", "pag_ini": 10, "pag_fim": 10, "texto": "prazo para defesa escrita do acusado"},
    {"doc": "Ementário 3ª ed.", "pag_ini": 45, "pag_fim": 45,
     "texto": "estabilidade dos membros da comissão disciplinar exigida"},
]


def test_nome_curto():
    assert nome_curto("MANUAL DE PROCESSO ADMINISTRATIVO DISCIPLINAR (2025)") == "Manual PAD"
    assert nome_curto(
        "SECRETARIA DE INTEGRIDADE PRIVADA MANUAL DE RESPONSABILIZAÇÃO DE ENTES PRIVADOS (3ª edição) (2026)"
    ) == "Manual PAR 3ª ed."
    assert nome_curto(
        "EMENTÁRIO DE NOTAS TÉCNICAS Uniformização de entendimentos (3ª edição) (2026)",
        "Nota Técnica nº 356/2022/CGUNE/CRG",
    ) == "Ementário 3ª ed. (NT 356/2022)"


def test_escolhe_o_trecho_que_sustenta_a_resposta():
    esc = escolher_fontes("A estabilidade é exigida dos membros da comissão disciplinar.", TRECHOS)
    assert [t["pag_ini"] for t in esc] == [45]


def test_sem_sobreposicao_cai_no_primeiro_trecho():
    esc = escolher_fontes("Sim.", TRECHOS)
    assert esc == [TRECHOS[0]]


def test_anexa_fonte_e_remove_citacao_do_modelo():
    trechos = [{"doc": "Manual PAD", "pag_ini": 400, "pag_fim": 401,
                "texto": "extrapolacao de prazos meras irregularidades nao anula"}]
    out = anexar_fonte("Prazos extrapolados são meras irregularidades. [Manual, págs 1-2]", trechos)
    assert out == "Prazos extrapolados são meras irregularidades.\n\nFonte: Manual PAD, págs 400-401"


def test_nao_encontrei_fica_sem_fonte():
    assert anexar_fonte("Não encontrei nos documentos.", TRECHOS) == "Não encontrei nos documentos."


def test_sem_consulta_a_resposta_fica_intacta():
    # uma pagina citada sem consulta precisa continuar visivel para a metrica citou_sem_consultar
    txt = "Conforme [Manual PAD, págs 10-11], o prazo é de 60 dias."
    assert anexar_fonte(txt, []) == txt


def test_limpar_remove_linha_fonte():
    assert limpar_citacao_do_modelo("Resposta.\nFonte: Manual PAD, pág. 3") == "Resposta."


def test_mescla_paginas_do_mesmo_documento():
    from cgu_rag.agente.citacao import montar_fonte
    esc = [
        {"doc": "Manual PAD", "pag_ini": 114, "pag_fim": 114},
        {"doc": "Manual PAD", "pag_ini": 114, "pag_fim": 115},
    ]
    assert montar_fonte(esc) == "Fonte: Manual PAD, págs 114-115"


def test_documentos_diferentes_e_paginas_separadas():
    from cgu_rag.agente.citacao import montar_fonte
    esc = [
        {"doc": "Manual PAD", "pag_ini": 10, "pag_fim": 10},
        {"doc": "Ementário 3ª ed.", "pag_ini": 45, "pag_fim": 45},
        {"doc": "Manual PAD", "pag_ini": 200, "pag_fim": 201},
    ]
    assert montar_fonte(esc) == "Fonte: Manual PAD, pág. 10, págs 200-201; Ementário 3ª ed., pág. 45"
