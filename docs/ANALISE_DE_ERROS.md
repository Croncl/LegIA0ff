# Analise de erros do agente (modelos locais, ate 16/11/2026)

Resumo: os modelos falhavam sobretudo ao decidir consultar a base. Sem consulta, respondiam de memoria e inventavam fontes. Quando consultavam, quase sempre acertavam a secao.

| Tipo | Descricao | Evidencia |
|---|---|---|
| 1. Nao consultou | resposta direta, sem ferramenta | Jurema 0%; Qwen2.5-7B 13%; Qwen2.5-3B 57%; Nemotron 80% (parte eram perguntas mal formadas do gabarito) |
| 2. Alucinou | sem trechos, inventou leis, artigos ou paginas | Jurema ("Lei 13.966/2019", "art. 115 da Lei 8.112"); Spark sem raciocinio ("Codigo de Defesa do Consumidor"); Qwen2.5-7B citou pagina sem consultar em 19% das respostas |
| 3. Buscou mal | consultou, mas a consulta nao trouxe a secao esperada | Nemotron com raciocinio ligado: 3 consultas sem a secao; desligado: 24 de 24 |
| 4. Nao rebuscou | o primeiro trecho nao respondia e o modelo desistiu | Qwen2.5-3B nos testes manuais |
| 5. Afirmou sem consultar | disse "nao encontrei nos documentos" sem ter procurado | Nemotron nas perguntas mal formadas |
| 6. Erro do teste | pergunta do gabarito mal formada (enunciado no lugar de pergunta) | q14, q16, q26, q27, q30; o modelo agiu certo e a metrica o puniu |

Causas: responder e o padrao do modelo; usar ferramenta e habito de treinamento (o Jurema ajustado para direito perdeu esse habito); prompt longo reduz o uso da ferramenta nos modelos pequenos; o raciocinio muda o comportamento (Spark so consulta com ele ligado; Nemotron fica melhor sem ele).

Mitigacao: guardrail de grounding (forcar a consulta em pergunta normativa) e fontes anexadas pelo sistema a partir dos trechos recuperados.
