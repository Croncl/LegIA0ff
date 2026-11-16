
## Removidos em 05/11/2026
| Tag | Motivo | Evidencia | Espaco liberado | Como recuperar |
|---|---|---|---|---|
| jurema-7b e hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF | Nao usa a ferramenta de consulta dentro do grafo e inventa leis e artigos quando responde sem consultar | 0 de 8 perguntas consultadas no benchmark (n = 8) e 0 de 2 no teste manual; ver docs/RESULTADOS.md e o diario (R7b) | 4,7 GB | `ollama pull hf.co/mauroneto/Jurema-7B-Q4_K_M-GGUF:latest` e `ollama create jurema-7b -f models/Modelfile.jurema-7b` |
| SparkLLM/Spark-X2.6-4B:latest (BF16) | Nao usado: os testes usam a versao Q8_0 | inventario de 05/11/2026 | 8,2 GB | `ollama pull SparkLLM/Spark-X2.6-4B:latest` |
| Spark-X2.6-4B-Q8:latest | Alias duplicado de SparkLLM/Spark-X2.6-4B:q8_0 (mesmo ID 2d3a7d5f159f) | ollama list | 0 (os arquivos sao compartilhados) | `ollama cp SparkLLM/Spark-X2.6-4B:q8_0 Spark-X2.6-4B-Q8` |

## Candidatos a comparar
| Modelo | Situacao | Observacao |
|---|---|---|
| SparkLLM/Spark-X2.6-4B:q8_0 | instalado | ponto de partida |
| qwen2.5:3b | instalado | rapido; 75% de consulta no benchmark preliminar |
| qwen2.5:7b | a baixar | o teste de 30/10 foi invalido (modelo nao instalado) |
| NVIDIA Nemotron 3.5 Bolt E4B (Q4_K_M, repositorio oficial da NVIDIA) | a baixar | 8B no total e 4B efetivos, base Gemma 4, 64K de contexto, ferramentas em varias rodadas, raciocinio configuravel, licenca OpenMDW-1.1; lancado em 23/10/2026 (fontes secundarias; conferir o model card). NVIDIA recomenda temperatura 1,0; o projeto usa 0,1 para todos |
| qwen3.8:27b (Q4_K_M) | instalado | referencia de qualidade, fora do uso interativo |

Fora da comparacao: Qwen3.8-27B FP8 (exige GPU grande e vLLM ou Transformers; nao roda no Ollama em CPU, e o Q4_K_M ja esta instalado).

## Removidos em 07/11/2026 (limpeza do 27B)
| Item | Motivo | Espaco liberado |
|---|---|---|
| alias qwen2.5-27b:instruct | Nome enganoso: nao existe Qwen2.5 de 27B; era o qwen3.8:27b | 0 (arquivos compartilhados) |
| C:\Modelos\qwen-base.gguf | Copia do arquivo do Ollama, criada para quantizar manualmente | 16,8 GB |

Quantizacao manual do 27B descartada: o qwen3.8:27b do Ollama ja e Q4_K_M; um Q5_K_M a partir dele seria requantizacao, sem ganho de qualidade; o llama.cpp local (build 4400) nao reconhece a arquitetura qwen35. Um Q5_K_M so seria valido se baixado pronto, e o 27B e apenas modelo de referencia.

## Candidatos adicionais (16/11/2026) - a triar
| Modelo (tag) | Situacao | Observacao |
|---|---|---|
| qwen3:8b (Q4_K_M) | a baixar | Qwen3 tem ferramentas e raciocinio desligavel; nao ha evidencia de "Qwen3.8-8B" (so o 27B foi encontrado); o desempenho do 27B nao permite inferir o do 8B |
| llama3.1:8b (Q4_K_M) | a baixar | ferramentas nativas; tende a chamar ferramenta demais (os controles de conversa medem isso); Q5 e Q6 ficam para a etapa de quantizacao |
| gemma4:e4b | a baixar (confirmar a tag na biblioteca) | ferramentas e raciocinio; o Nemotron Bolt E4B e construido sobre o Gemma 4 E4B; compara modelo-base e versao agentica |
| mistral-nemo:12b (Q4_K_M) | so triagem | 12B em CPU deve ser lento; so segue se o tempo for aceitavel |
| qwen3.5:4b | opcional | so se ja estiver instalado |

## Excluidos sem medicao (16/11/2026)
| Modelo | Motivo |
|---|---|
| gemma3 (4b, 12b, 27b) | Nenhuma tag do Gemma 3 aceita ferramentas no Ollama (apenas visao); o erro e imediato. Fontes: guias de compatibilidade de ferramentas do Ollama. Existe versao de comunidade com chamada de funcao, nao oficial |

Regra de triagem: so segue para a medicao o modelo que listar "tools" nas Capabilities do ollama show.

## Triagem de capacidades (16/11/2026, ollama show)
| Modelo | Parametros | Quantizacao | Contexto maximo | Capacidades | Resultado |
|---|---|---|---|---|---|
| qwen3:8b | 8,2 B | Q4_K_M | 40.960 | tools, thinking | segue para a triagem de uso |
| llama3.1:8b | 8,0 B | Q4_K_M | 131.072 | tools | segue para a triagem de uso |
| gemma4:e4b | 7,5 B | Q4_K_M | 131.072 | vision, tools, thinking | segue; mesmo numero de parametros do Nemotron Bolt E4B (7,52 B), coerente com a base comum citada pelas fontes |
| mistral-nemo:12b | 12,2 B | Q4_0 (diferente das demais) | 1.024.000 | tools | segue; a quantizacao difere dos outros modelos, entao a comparacao exige cautela |
