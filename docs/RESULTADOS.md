# Resultados

## Baseline de recuperacao (A1 e A2), 30/10/2026
Gabarito: 30 perguntas sinteticas revisadas manualmente (D-08), com campo `fase` (D-11).
Acerto estrito: mesmo documento, mesma secao e paginas sobrepostas.
Corpus: 6 PDFs publicos da CGU, 1567 trechos. Embeddings: `intfloat/multilingual-e5-small`.

| Experimento | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 | s/consulta |
|---|---|---|---|---|---|---|
| A1 BM25 | 0.500 | 0.833 | 0.867 | 0.967 | 0.674 | 0.009 |
| A2 BM25+vetores (RRF) | 0.500 | 0.900 | 0.933 | 0.967 | 0.695 | 0.412 |

hit@5 por grupo (A1 -> A2). Pergunta de varias fases conta em cada uma; os grupos se sobrepoem.

| Grupo | n | A1 | A2 |
|---|---|---|---|
| admissibilidade | 9 | 0.889 | 1.000 |
| acusatoria | 11 | 0.818 | 0.909 |
| julgamento | 8 | 0.875 | 1.000 |
| par | 6 | 0.833 | 1.000 |
| fora_do_fluxo | 8 | 0.875 | 0.875 |

Figuras: `docs/img/03_comparacao.png`, `docs/img/04_progresso.png`, `docs/img/05_por_grupo.png`.

### Leitura
- Recall bom (hit@10 = 0.967) e ordenacao fraca (hit@1 = 0.5): em metade das perguntas a secao certa nao vem em primeiro.
- A busca hibrida acerta 2 perguntas a mais no top-5 (26 para 28 de 30) e sobe 0.02 no MRR. Com n = 30 cada pergunta vale 0.033; a diferenca e pequena e sem forca estatistica.
- Custo da busca hibrida: cerca de 46 vezes mais tempo por consulta (0.412 s contra 0.009 s), ainda abaixo de meio segundo.
- Candidatos para melhorar a ordenacao: reranker, embedding com janela maior (bge-m3, D-06) e metadados do LegalNLP.

### Limites
- O acerto estrito pode penalizar secoes vizinhas que tambem respondem a pergunta.
- Perguntas sinteticas, mesmo revisadas, tendem a favorecer a busca lexical.
- Grupos pequenos (n de 6 a 11): diferencas de uma pergunta mudam muito os percentuais.

## Agente: medicao robusta (medir_agente v2: 30 perguntas + 6 controles, 07/11/2026)
Criterios da D-17 (proposta): consulta >= 90%; no maximo 1 de 4 conversas simples consultada; zero citacao sem consulta; no maximo 1 erro; mediana ate 60 s. Temperatura 0,1; contexto 8192; Ollama 0.40.15; commit 51ae0ee.

| Modelo (raciocinio) | Consultou | Acerto | Consultas/pergunta | Conversas simples consultadas | Citou sem consultar | Erros | Mediana (s) | Veredito |
|---|---|---|---|---|---|---|---|---|
| Nemotron 3.5 Bolt E4B Q4_K_M (desligado) | 80% | 80% | 0,80 | 0 de 4 | 0 | 0 | 19,3 | REPROVADO: consultou 80% (minimo 90%) |

Leitura: das 24 perguntas em que consultou, a secao esperada veio nas 24. Nas 6 sem consulta a resposta saiu em 1 a 3 s (conteudo a verificar: a metrica so detecta citacao de pagina). Aquecimento: 68,8 s. Os limites do criterio nao foram alterados depois do resultado.

## Baseline de recuperacao com o gabarito reescrito (17/11/2026)
Gabarito: 30 perguntas curtas (media de 77 e maximo de 96 caracteres), escritas a partir do campo `esperado`; os enunciados antigos ficam em `data/gabarito/*_antigo_enunciados.jsonl`. Os resultados das secoes acima (07/11) usam o gabarito ANTIGO (enunciados longos) e ficam como historico. Mesma metrica estrita (mesmo documento e paginas sobrepostas), ate k = 10.

| Metodo | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 | s/consulta |
|---|---|---|---|---|---|---|
| A1 BM25 | 0,433 | 0,767 | 0,833 | 0,933 | 0,613 | 0,009 |
| A2 BM25 + vetores (multilingual-e5-small, RRF) | 0,433 | 0,867 | 0,967 | 1,000 | 0,643 | 0,422 |

Por fase (hit@5 / MRR@10), A1 e A2:

| Fase | n | A1 | A2 |
|---|---|---|---|
| fora_do_fluxo | 10 | 0,900 / 0,617 | 1,000 / 0,578 |
| admissibilidade | 7 | 1,000 / 0,857 | 1,000 / 0,833 |
| acusatoria | 9 | 0,778 / 0,622 | 1,000 / 0,726 |
| par | 6 | 0,833 / 0,519 | 0,833 / 0,441 |
| julgamento | 6 | 0,667 / 0,611 | 1,000 / 0,917 |

### Leitura
- A busca hibrida acerta 4 perguntas a mais no top-5 (25 para 29 de 30; intervalo de confianca de 95% de Wilson: cerca de 0,66 a 0,93 contra 0,83 a 0,99). Mesmo no melhor caso (4 a favor e 0 contra), o teste exato de McNemar da p = 0,125: a diferenca nao e significativa com n = 30.
- Com perguntas curtas, a vantagem do hibrido em hit@5 passou de 0,07 (gabarito antigo) para 0,13: os enunciados longos repetiam o vocabulario da resposta e favoreciam a busca lexical.
- hit@1 = 0,433: a pagina certa so e a primeira em 43% dos casos. O agente le k = 4 trechos, entao o desempenho esperado fica entre hit@3 (0,867) e hit@5 (0,967).
- A latencia de 0,42 s confirma que o 1,34 s medido antes da troca do gabarito era ruido da maquina.

### Limites
- O acerto estrito exige o mesmo documento e paginas sobrepostas: paginas validas de outro documento contam como erro (ex.: q18, resposta correta no Manual PAD, gabarito no Ementario). Os numeros sao um piso.
- Grupos por fase tem n de 6 a 10: nao se tira conclusao por fase.

## Agente: Nemotron em 17/11/2026 (prompt antigo, gabarito antigo): sem valor de veredito
Nemotron 3.5 Bolt E4B Q4_K_M, raciocinio desligado, Ollama 0.40.16, commit 2e0dfa5: consultou 80% (24 de 30), acerto 24 de 24 quando consultou, 0 erros, 0 citacoes sem consulta, mediana 21,6 s; D-17 REPROVADO so em consulta. As 6 perguntas sem consulta (q14, q16, q24, q26, q27 e q30) eram enunciados ("A questao aborda...", "Para resolver esta questao...") e nao perguntas; a q27 estava truncada. A medicao sera refeita com a D-18 e o gabarito reescrito.
