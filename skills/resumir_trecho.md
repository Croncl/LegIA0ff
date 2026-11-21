# Skill: Resumir Trecho Normativo

Use esta skill quando o usuário pedir um resumo de um trecho ou quando o trecho recuperado for longo demais para responder diretamente.

## Passos

1. Identifique o trecho relevante retornado por `consultar_base`.
2. Chame a ferramenta `resumir_trecho` passando o texto do trecho.
3. Apresente os bullet points retornados, sem adicionar informação extra.
4. Se o usuário quiser mais detalhes, consulte a base novamente com termo mais específico.
