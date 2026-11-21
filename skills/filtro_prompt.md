# Skill: Filtro de Prompt (Guardrail de Entrada)

Aplicada automaticamente antes de qualquer consulta ao agente.

## Passos

1. Tokenize o prompt do usuário, removendo stopwords em português.
2. Conte as palavras relevantes restantes.
3. Se a contagem ultrapassar 20 palavras úteis, bloqueie e retorne mensagem de aviso.
4. Se passar no filtro, encaminhe normalmente ao grafo.
