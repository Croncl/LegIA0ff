# LegalNLP — Assistente RAG Agêntico CGU (PAD e PAR)

**Disciplina:** Processamento de Linguagem Natural — Pós-Graduação  
**Dupla:** Cristovão Lacerda Cronje · Olive Oliveira Medeiros  
**Repositório:** github.com/Croncl/LegalNLP (branch `main`)

---

## Visão Geral

Sistema de Recuperação Aumentada por Geração (RAG) agêntico para consultas sobre:

- **PAD** — Processo Administrativo Disciplinar (Lei 8.112/90, Manual CGU)
- **PAR** — Processo Administrativo de Responsabilização (Lei 12.846/13, Manual CGU)

O agente usa **LangGraph** para orquestrar ferramentas, **Ollama** para inferência local (sem envio de dados à nuvem) e **Streamlit** para a interface.

---

## Arquitetura

```
Pergunta do usuário
       │
       ▼
filtro_prompt (R11) ── prompt longo? ── SIM → mensagem One-Punch Man
       │ NÃO
       ▼
   LangGraph (grafo.py)
       │
       ├── consultar_base   → BM25 + vetores RRF, corpus 6 PDFs / 1567 trechos
       ├── buscar_web       → DuckDuckGo (normas não indexadas)
       ├── buscar_url       → fetch de URLs (DOU, LegisWeb, CGU)
       └── resumir_trecho   → resumo em 3 bullets via LLM
       │
       ▼
   citacao.py → anexa Fonte + página (sistema, não o modelo)
       │
       ▼
   Resposta (≤3 frases, ≤300 tokens)
```

---

## Estrutura do Projeto

```
app/
  app.py                    UI Streamlit (R12)
src/cgu_rag/
  config.py                 variáveis de ambiente (.env)
  busca.py                  BM25 + vetores + RRF
  agente/
    grafo.py                grafo LangGraph (R7/R11)
    ferramentas.py          consultar_base (R7)
    mcp_cgu.py              servidor MCP próprio FastMCP (R8)
    mcp_comunidade.py       MCPs da comunidade: DuckDuckGo + fetch (R9)
    skills.py               resumir_trecho + filtro_prompt (R10/R11)
    citacao.py              anexa fonte e página (D-18)
    modelo.py               cliente Ollama via LangChain
scripts/
  ingerir.py                ingestão de PDFs para o corpus
  medir_agente.py           medição robusta (D-17)
  gabarito.py               gestão do gabarito de 30 perguntas
  avaliar.py                hit@k, MRR, baseline
docs/
  DECISOES.md               registro de todas as decisões do projeto
  DIARIO.md                 diário de desenvolvimento
  RESULTADOS.md             resultados das medições
  MODELOS.md                modelos testados e descartados
data/
  pdfs/                     corpus (não versionado)
  gabarito/perguntas.jsonl  30 perguntas curtas com gabarito
```

---

## Instalação

**Requisitos:** Python 3.11, [Ollama](https://ollama.com) instalado e rodando.

```bash
# 1. Clone e instale
git clone https://github.com/Croncl/LegalNLP
cd LegalNLP
pip install -e ".[dev]"

# 2. Configuração
cp .env.example .env
# Edite .env se necessário (padrão: gemma4:e4b, Ollama local)

# 3. Modelo
ollama pull gemma4:e4b

# 4. Corpus (coloque os PDFs da CGU em data/pdfs/ e ingira)
python scripts/ingerir.py

# 5. Testes
pytest

# 6. UI
streamlit run app/app.py
```

---

## Modelos Testados

| Modelo | Consulta | Acerto | Mediana | Veredicto |
|---|---|---|---|---|
| **gemma4:e4b** (finalista) | 100% | **93,3%** | **11,9 s** | ✅ APROVADO |
| Nemotron Q4_K_M (reserva) | 100% | 90,0% | 13,6 s | ✅ APROVADO |
| qwen3:8b | 96,7% | 86,7% | 34,5 s | ✅ lento |
| qwen2.5:3b | 3,3% | 3,3% | 0,6 s | ❌ REPROVADO |

Critérios D-17: consulta ≥90%, conversas simples ≤1/4 consultadas, 0 citações sem consulta, ≤1 erro, mediana ≤60 s.

---

## 10 Testes Documentados

### Teste 1 — Pergunta normativa básica
**Entrada:** `quais os casos de demissão da 8112?`  
**Esperado:** lista dos casos do art. 132 com fonte  
**Resultado:** ✅ resposta correta com `Fonte: Manual PAD, pág. 252`

### Teste 2 — Pergunta sobre TAC
**Entrada:** `quando se aplica TAC?`  
**Esperado:** resposta sobre Termo de Ajustamento de Conduta  
**Resultado:** ✅ após correção do docstring de `buscar_web` (fix: ambiguidade TAC)

### Teste 3 — Guardrail filtro_prompt (prompt longo)
**Entrada:** frase com >20 palavras relevantes (sem stopwords)  
**Esperado:** mensagem One-Punch Man, sem invocar o LLM  
**Resultado:** ✅ `Erro 404: Paciência não encontrada...`

### Teste 4 — Conversa simples (não deve consultar)
**Entrada:** `Oi, tudo bem?`  
**Esperado:** resposta em 1 frase, 0 consultas à base  
**Resultado:** ✅ `controles_consultados = 0/4`

### Teste 5 — Fora de escopo
**Entrada:** `Qual é a capital da França?`  
**Esperado:** resposta sem consultar a base  
**Resultado:** ✅ `fora_de_escopo_consultou = 0/2`

### Teste 6 — Fonte anexada pelo sistema
**Entrada:** pergunta normativa qualquer  
**Esperado:** resposta com `Fonte:` anexada pelo `citacao.py`, não pelo modelo  
**Resultado:** ✅ `citou_sem_consultar = 0.0` em 30 perguntas

### Teste 7 — Limite de tokens
**Entrada:** pergunta que gera resposta longa  
**Esperado:** resposta truncada com `truncada=True` no estado  
**Resultado:** ✅ campo `truncada` registrado corretamente

### Teste 8 — MCP próprio (R8)
**Entrada:** `python -c "from cgu_rag.agente.mcp_cgu import mcp; print(mcp.name)"`  
**Esperado:** `cgu-rag`  
**Resultado:** ✅

### Teste 9 — MCPs comunidade (R9)
**Entrada:** `from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web; print([x.name for x in criar_ferramentas_web()])`  
**Esperado:** `['buscar_web', 'buscar_url']`  
**Resultado:** ✅

### Teste 10 — Medição agente (D-17)
**Entrada:** `python scripts/medir_agente.py --modelo gemma4:e4b --pensar false`  
**Esperado:** APROVADO nos critérios D-17  
**Resultado:** ✅ consultou 100%, acerto 93,3%, mediana 11,9 s, 0 erros

---

## Decisões Principais

Ver `docs/DECISOES.md` para o registro completo. Resumo:

- **D-17:** critérios de aprovação de modelo (consulta ≥90%, mediana ≤60 s)
- **D-18:** resposta ≤3 frases, fonte anexada pelo sistema, limite 300 tokens
- **D-19:** gemma4:e4b escolhido como modelo padrão (93,3% acerto, 11,9 s)

---

## Roadmap Fase 2

- Classificador Laya (ModernBERT) para tipificação de pedidos
- RAG estruturado com LLMs autorregressivos
- Extração automática de normativos do DOU via MCP
- Compactação automática de histórico de conversas
