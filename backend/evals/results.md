# Resultados da avaliação da IA

Gerado por `python -m evals.run_evals`. Cada linha é uma rodada; o relatório completo está em `evals/runs/`.
Perfil fictício e vagas em `evals/fixtures/`. Custos são estimativas.

| Data | Modelo | Rótulo | Vagas | Cobertura | Precisão | Análise | Invenções pegas | Falsos alarmes | Custo/vaga | Custo/texto |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-18 13:56 * | claude-opus-5-5 | baseline | 10 | 100% | 100% | 84% | 100% | 0% | US$ 0.0746 | US$ 0.0576 |
| 2026-11-18 14:03 * | claude-sonnet-5-5 | baseline | 10 | 100% | 100% | 86% | 100% | 0% | US$ 0.0412 | US$ 0.0273 |
| 2026-11-18 14:09 * | claude-haiku-5-5 | baseline | 10 | 100% | 100% | 84% | 86% | 0% | US$ 0.0025 | US$ 0.0018 |

\* gabarito ainda não revisado à mão: números provisórios.
