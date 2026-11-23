# LegIA0ff — Assistente RAG Agêntico para Legislação (PAD e PAR)

**Disciplina:** Processamento de Linguagem Natural — Pós-Graduação  
**Dupla:** Cristovão Lacerda Cronje · Olive Oliveira Medeiros  
**Repositório:** github.com/Croncl/LegIA0ff (branch `main`)

---

## Visão Geral

Sistema de Recuperação Aumentada por Geração (RAG) agêntico para consultas sobre:

- **PAD** — Processo Administrativo Disciplinar (Lei 8.112/90, Manual CGU)
- **PAR** — Processo Administrativo de Responsabilização (Lei 12.846/13, Manual CGU)

O agente usa **LangGraph** para orquestrar ferramentas, **Ollama** para inferência local (sem envio de dados à nuvem) e **Streamlit** para a interface.

**Modelo padrão:** `gemma4:e4b` (D-19) — 93,3% de acerto, mediana 11,9 s.

---

## Arquitetura do Grafo

```
Pergunta do usuário
       │
       ▼
┌─────────────────┐
│  nó: entrada    │ ← guardrail de entrada (R11)
│  • msg vazia?   │   risco 1: mensagem vazia → bloqueio
│  • filtro_prompt│   risco 2: prompt longo (>20 palavras úteis) → bloqueio
└────────┬────────┘
         │ bloqueado?
    SIM ─┤                    NÃO
         ▼                     ▼
┌──────────────┐     ┌─────────────────┐
│  nó: saida   │     │  nó: responder  │ ← modelo decide: responder ou consultar
└──────────────┘     └────────┬────────┘
                              │ chamou ferramenta?
                         SIM ─┤               NÃO
                              ▼                ▼
                   ┌─────────────────┐  ┌──────────────┐
                   │ nó: ferramentas │  │  nó: saida   │ ← guardrail de saída
                   │ consultar_base  │  │  citacao.py  │   resposta vazia → aviso
                   │ buscar_web      │  │  ≤500 tokens │
                   │ buscar_url      │  └──────────────┘
                   │ resumir_trecho  │
                   │ resumir_conversa│
                   │ transparencia_* │
                   │ cnpj_*          │
                   └────────┬────────┘
                            │ (volta ao responder, até 3x)
                            ▼
                   ┌─────────────────┐
                   │  nó: responder  │
                   └─────────────────┘
```
[![Architecture diagram of croncl/legia0ff](https://gitdiagram.com/croncl/legia0ff/diagram.png)](https://gitdiagram.com/croncl/legia0ff?utm_source=readme&utm_medium=picture)

**Função de cada nó:**
- `entrada`: normaliza o turno, aplica guardrails de entrada (mensagem vazia + prompt longo)
- `responder`: o modelo decide chamar ferramenta ou responder diretamente
- `ferramentas`: executa as ferramentas chamadas pelo modelo; resultado volta ao `responder`
- `saida`: anexa fonte/página via `citacao.py`, aplica guardrail de saída, registra metadados

---

## Componentes

### RAG Agêntico
- **Corpus:** 6 PDFs da CGU (Manuais PAD e PAR, leis correlatas) — 1567 trechos indexados
- **Busca híbrida:** BM25 + vetores com RRF (hit@5 = 0,967)
- **Comportamento:** o modelo consulta `consultar_base`, reformula a query com sinônimos se necessário, até 3 tentativas por turno

### MCP
- **Servidor próprio (`mcp_cgu.py`):** ferramentas específicas do domínio CGU, implementado com FastMCP (stdio)
- **Servidor comunidade (`mcp_comunidade.py`):** `buscar_web` (DuckDuckGo) e `buscar_url` (fetch)
- **Transparência (`mcp_transparencia.py`):** `transparencia_sancoes`, `transparencia_pep`, `transparencia_despesas_favorecido`, `cnpj_consultar`, `cnpj_processos`

### Skills
- **`resumir_trecho`** (`skills/resumir_trecho.md`): resume trecho normativo em até 3 bullet points via LLM, sob demanda
- **`filtro_prompt`** (`skills/filtro_prompt.md`): guardrail de entrada — tokeniza, remove stopwords, bloqueia prompts com >20 palavras úteis
- **`resumir_conversa`** (`skills/`): resume o histórico da conversa atual em bullet points, acionada quando o usuário pede resumo do chat

### Memória
- `MemorySaver` do LangGraph com `thread_id` por conversa
- Histórico persistido em `data/historico_chats/{thread_id[:8]}.json`
- Interface permite carregar conversas anteriores e iniciar nova thread

### Guardrails
- **Entrada (nó `entrada`):** bloqueia mensagem vazia e prompt longo (>20 palavras úteis sem stopwords)
- **Saída (nó `saida`):** bloqueia resposta vazia ou com menos de 10 caracteres, retorna mensagem de aviso

---

## Estrutura do Projeto

```
app/
  app.py                    UI Streamlit (R12)
  ui_estilo.py              CSS e componentes visuais
  ui_grafo.py               mapa de conhecimento (pyvis)
src/cgu_rag/
  config.py                 variáveis de ambiente (.env)
  busca.py                  BM25 + vetores + RRF
  agente/
    grafo.py                grafo LangGraph (R7/R11)
    ferramentas.py          consultar_base (R7)
    mcp_cgu.py              servidor MCP próprio FastMCP (R8)
    mcp_comunidade.py       MCPs da comunidade: DuckDuckGo + fetch (R9)
    mcp_transparencia.py    Transparência CGU via REST (R9)
    skills.py               resumir_trecho + filtro_prompt (R10/R11)
    citacao.py              anexa fonte e página (D-18)
    modelo.py               cliente Ollama via LangChain
skills/
  resumir_trecho.md         catálogo da Skill A
  filtro_prompt.md          catálogo da Skill C
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

### Windows

```powershell
# 1. Clone o repositório
git clone https://github.com/Croncl/LegIA0ff
cd LegIA0ff

# 2. Configuração automática (cria env conda, instala dependências e .env)
./configurar-cgu-rag.ps1

# 3. Modelo
ollama pull gemma4:e4b

# 4. Corpus (coloque os PDFs em data/pdfs/ e ingira)
conda activate legia0ff
python scripts/ingerir.py

# 5. Testes
pytest

# 6. UI
streamlit run app/app.py
```

### Linux / Debian

```bash
# 1. Clone o repositório
git clone https://github.com/Croncl/LegIA0ff
cd LegIA0ff

# 2. Instalar Miniconda (se necessário)
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
~/miniconda3/bin/conda init bash
source ~/.bashrc

# 3. Configuração automática
chmod +x configurar-cgu-rag.sh
./configurar-cgu-rag.sh

# 4. Modelo
ollama pull gemma4:e4b

# 5. Corpus (coloque os PDFs em data/pdfs/ e ingira)
conda activate legia0ff
python scripts/ingerir.py

# 6. Testes
pytest

# 7. UI
streamlit run app/app.py
```

> **Verificação do modelo ativo:** `ollama ps` no terminal, ou veja o rodapé da sidebar na UI.

**Variáveis de ambiente (`.env`):**

| Variável | Padrão | Descrição |
|---|---|---|
| `LLM_MODEL` | `gemma4:e4b` | Modelo Ollama |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Endpoint Ollama |
| `LLM_API_KEY` | `ollama` | Chave (fixo para Ollama local) |
| `SIGILO` | `sigiloso` | `sigiloso` = só local; `publico` = permite API externa |
| `RAG_DB` | `data/rag_cgu.db` | Caminho do banco SQLite |
| `RAG_EMB_MODEL` | `intfloat/multilingual-e5-small` | Modelo de embeddings |
| `MCP_AI_KEY` | _(vazio)_ | Chave MCP.ai (opcional) |
| `TRANSPARENCIA_API_KEY` | _(vazio)_ | Chave Transparência (opcional) |
---

## Modelos Testados

| Modelo | Consulta | Acerto | Mediana | Veredicto |
|---|---|---|---|---|
| **gemma4:e4b** (padrão) | 100% | **93,3%** | **11,9 s** | ✅ APROVADO |
| Nemotron Q4_K_M (reserva) | 100% | 90,0% | 13,6 s | ✅ APROVADO |
| qwen3:8b | 96,7% | 86,7% | 34,5 s | ✅ lento |
| qwen2.5:3b | 3,3% | 3,3% | 0,6 s | ❌ REPROVADO |

Critérios D-17: consulta ≥90%, conversas simples ≤1/4 consultadas, 0 citações sem consulta, ≤1 erro, mediana ≤60 s.

---

## 10 Testes Documentados

Taxa de acerto: **10/10 (100%)** — sem falhas nos testes documentados.

### Teste 1 — Pergunta normativa básica
**Entrada:** `quais os casos de demissão da 8112?`  
**Esperado:** lista dos casos do art. 132 com fonte anexada  
**Obtido:** resposta listando os casos do art. 132 com `Fonte: Manual PAD, pág. 252`  
**Resultado:** ✅ APROVADO

### Teste 2 — Reformulação de consulta (desafiador)
**Entrada:** `quando se aplica TAC?`  
**Esperado:** resposta sobre Termo de Ajustamento de Conduta com fonte  
**Obtido:** primeira consulta retornou trechos genéricos; agente reformulou para "termo ajustamento conduta PAR" e obteve trecho correto  
**Resultado:** ✅ APROVADO — testou o limite da reformulação automática

### Teste 3 — Guardrail de entrada: prompt longo
**Entrada:** frase com >20 palavras relevantes (sem stopwords)  
**Esperado:** mensagem de bloqueio, sem invocar o LLM  
**Obtido:** `Erro 404: Paciência não encontrada. Seja objetivo e resuma em 20 palavras ou menos!`  
**Resultado:** ✅ APROVADO

### Teste 4 — Conversa simples (não deve consultar)
**Entrada:** `Oi, tudo bem?`  
**Esperado:** resposta em 1 frase, 0 consultas à base  
**Obtido:** `Tudo bem! Como posso ajudar com PAD ou PAR?` — `ferramentas = []`  
**Resultado:** ✅ APROVADO

### Teste 5 — Fora de escopo (desafiador)
**Entrada:** `Qual é a capital da França?`  
**Esperado:** resposta direta sem consultar a base  
**Obtido:** resposta em 1 frase sem chamar `consultar_base`  
**Resultado:** ✅ APROVADO — modelo reconheceu escopo sem instrução explícita de recusa

### Teste 6 — Fonte anexada pelo sistema, não pelo modelo
**Entrada:** `qual o prazo para conclusão do PAD?`  
**Esperado:** fonte e página anexadas pelo `citacao.py`, modelo não escreve "Fonte:"  
**Obtido:** resposta sem menção a fonte no corpo; `Fonte: Manual PAD, pág. 87` anexado pelo sistema  
**Resultado:** ✅ APROVADO — `citou_sem_consultar = 0.0` em 30 perguntas

### Teste 7 — Guardrail de saída: resposta vazia
**Entrada:** pergunta com contexto propositalmente ambíguo para induzir resposta vazia  
**Esperado:** mensagem de aviso, sem retornar string vazia ao usuário  
**Obtido:** `⚠️ Não foi possível gerar uma resposta. Tente reformular a pergunta.`  
**Resultado:** ✅ APROVADO

### Teste 8 — MCP próprio (desafiador)
**Entrada:** `python -c "from cgu_rag.agente.mcp_cgu import mcp; print(mcp.name)"`  
**Esperado:** `cgu-rag`  
**Obtido:** `cgu-rag`  
**Resultado:** ✅ APROVADO

### Teste 9 — MCPs comunidade
**Entrada:** `from cgu_rag.agente.mcp_comunidade import criar_ferramentas_web; print([x.name for x in criar_ferramentas_web()])`  
**Esperado:** `['buscar_web', 'buscar_url']`  
**Obtido:** `['buscar_web', 'buscar_url']`  
**Resultado:** ✅ APROVADO

### Teste 10 — Medição robusta do agente (D-17)
**Entrada:** `python scripts/medir_agente.py --modelo gemma4:e4b --pensar false` (30 perguntas + 6 controles)  
**Esperado:** APROVADO nos critérios D-17  
**Obtido:** consulta 100%, acerto 93,3%, mediana 11,9 s, 0 erros, 0 citações sem consulta  
**Resultado:** ✅ APROVADO

---

### Análise de Erros

Nos 30 testes do gabarito, 2 perguntas foram respondidas incorretamente (6,7%):

- **Ambiguidade terminológica:** perguntas com termos que aparecem em contextos distintos no corpus (ex.: "comissão" referindo-se tanto à comissão processante quanto à comissão de ética) levaram o modelo a recuperar trechos do contexto errado.
- **Lacuna no corpus:** uma pergunta sobre prazo específico do PAR não tinha trecho correspondente nos 6 PDFs indexados; o modelo respondeu "Não encontrei nos documentos" corretamente, mas a ausência foi contabilizada como erro no gabarito.

Mitigação prevista na Fase 2: ampliação do corpus e GraphRAG para distinguir contextos por entidade.

---

## Decisões Principais

Ver `docs/DECISOES.md` para o registro completo. Resumo:

- **D-17:** critérios de aprovação de modelo (consulta ≥90%, mediana ≤60 s, ≤1 erro, 0 citações sem consulta)
- **D-18:** resposta ≤3 frases, fonte anexada pelo sistema, limite 300 tokens
- **D-19:** `gemma4:e4b` escolhido como modelo padrão (93,3% acerto, 11,9 s)

---

## Roadmap Fase 2

- **RAG estruturado** com LLMs autorregressivos para respostas sintéticas longas
- **MCP + GraphRAG local para normativos da CGU:**