# Avaliação da IA

Mede, contra a API real do Claude, se a IA do job-copilot funciona bem. Os testes em `tests/` verificam o código com o Claude simulado; esta pasta mede a qualidade das respostas do modelo.

## O que é medido

| Medida | Como |
|---|---|
| **Extração: cobertura** | Dos requisitos do gabarito, quantos o Claude extraiu |
| **Extração: precisão** | Dos requisitos extraídos, quantos estão no gabarito (os outros aparecem como "extraídos sem gabarito": inventados ou que faltam no gabarito) |
| **Extração: tipo e trilhas** | Obrigatório/desejável correto; número de trilhas correto |
| **Análise** | Casos claros (o perfil obviamente atende ou não atende) com o status certo |
| **Verificação** | Textos com afirmações inventadas plantadas: quantas a verificação pega e quantas verdadeiras marca por engano |
| **Custo** | Tokens, tempo e custo estimado por operação |

Tudo passa pelas mesmas rotas da API que o app usa, com um banco temporário em memória. O banco real (`data/`) nunca é usado.

## Arquivos

- `fixtures/profile.json`: perfil fictício (Marina, desenvolvedora backend). Nunca use o seu currículo real aqui.
- `fixtures/jobs/NN-*.txt`: 10 vagas fictícias (backend, frontend, fullstack em inglês, dados, IA, DevOps com ruído de página, uma vaga com duas trilhas).
- `fixtures/jobs/NN-*.expected.json`: o gabarito de cada vaga.
- `fixtures/planted_texts.json`: textos com invenções plantadas.
- `run_evals.py`: roda a avaliação. `scoring.py`: as contas, testadas em `tests/test_evals.py`.
- `runs/`: o relatório completo de cada rodada. `results.md`: tabela com todas as rodadas.

## Revisar o gabarito (antes dos números valerem)

Cada `.expected.json` tem:

```json
{
  "reviewed": false,
  "tracks": 1,
  "required": [{"text": "Experiência com Python", "match": ["python"]}],
  "preferred": [{"text": "Docker", "match": ["docker"]}],
  "analysis": [{"match": ["python"], "expected": "meets"}]
}
```

- `required` / `preferred`: um item por requisito que a vaga realmente pede, separado como o prompt de extração pede ("Python e Django" são dois itens).
- `match`: trechos que identificam o requisito. Sem acento e sem diferenciar maiúsculas; basta um deles aparecer no requisito extraído.
- `analysis`: só casos **óbvios** para o perfil fictício (`meets` ou `missing`). Deixe de fora os casos discutíveis.
- `track` (vaga com várias trilhas): palavra do título da trilha que deve ser analisada.

Leia cada vaga, confira a lista e mude `reviewed` para `true`. Enquanto algum arquivo estiver com `false`, o relatório avisa que os números são provisórios.

## Rodar

Dentro de `backend/`, com o ambiente virtual ativado:

```bash
python -m evals.run_evals                                   # modelos do .env (ANTHROPIC_MODEL + ANTHROPIC_MODELS)
python -m evals.run_evals --model claude-haiku-5-5 --label "haiku"   # um modelo só, em tudo
python -m evals.run_evals --models "extract_job=claude-haiku-5-5"    # outra combinação por operação
python -m evals.run_evals --jobs 01,09 --no-texts           # rodada rápida e barata
```

O script mostra quantas chamadas vai fazer e pede confirmação (`--yes` pula). Uma rodada completa faz cerca de 44 chamadas.

## Descobertas da primeira rodada (2026-11-18)

Uma rodada completa em cada modelo, com os prompts atuais (rótulo `baseline`). O gabarito ainda é o rascunho não revisado, então os números são provisórios. Relatórios completos em `runs/`.

| Modelo | Cobertura | Precisão | Análise | Invenções pegas | Falsos alarmes | Custo/vaga | Custo/texto |
|---|---|---|---|---|---|---|---|
| Opus 5.5 | 100% | 100% | 84% | 100% (7/7) | 0% | US$ 0.075 | US$ 0.058 |
| Sonnet 5.5 | 100% | 100% | 86% | 100% (7/7) | 0% | US$ 0.041 | US$ 0.027 |
| Haiku 5.5 | 100% | 100% | 84% | 86% (6/7) | 0% | US$ 0.0025 | US$ 0.0018 |

**1. A extração está resolvida, e o teste ficou fácil demais.** Os três modelos acertaram 100% dos requisitos, sem inventar nenhum e sem errar o número de trilhas, nem na vaga em inglês nem na vaga com lixo da página. Ou seja, esta medida não separa os modelos. Para separar, faltam vagas mais difíceis: requisitos escondidos no meio da descrição, "diferencial" misturado com "obrigatório", vagas mal formatadas.

**2. Todos os erros da análise são para o mesmo lado: o modelo responde "parcial".** Nenhum modelo trocou "atende" por "não atende" nem o contrário, e o código não rejeitou nenhuma evidência. Os erros se repetem entre os modelos:
- **Esperado "não atende", veio "parcial":** Oracle (o perfil tem PostgreSQL), Kubernetes (tem Docker), Jest (tem pytest). O modelo dá crédito por uma tecnologia parecida.
- **Esperado "atende", veio "parcial":** CI/CD (o perfil tem GitHub Actions), CSS. Django e Redis na vaga 09 também, no Opus e no Haiku: aparecem só na lista de skills, sem experiência que mostre o uso.

Boa parte desses casos é discutível. O gabarito trata como óbvio algo que não é tão óbvio assim. Antes de mexer no prompt de análise, vale revisar esses casos no gabarito. Se decidir que "tecnologia parecida" deve ser "não atende", aí sim a regra entra no prompt `analyze_job`.

**3. A verificação de textos funciona nos três, mas o Haiku deixou passar uma invenção.** "Inglês fluente" não foi marcado, e o perfil diz "Intermediário". É exatamente o tipo de exagero que a regra principal do projeto proíbe. Opus e Sonnet pegaram as 7 invenções e nenhum modelo marcou afirmação verdadeira por engano.

**4. O custo muda muito; a qualidade, quase nada.** O Haiku sai cerca de 30 vezes mais barato que o Opus e é o mais rápido (a análise leva uns 14s, contra 21s do Opus). O Sonnet custa cerca de metade do Opus, com a mesma qualidade. A análise da vaga é a operação mais cara em todos os modelos, por causa da saída longa.

**Recomendação provisória:**
- **Sonnet** para a verificação de textos (`extract_claims`), que protege a regra principal e onde o Haiku falhou.
- **Haiku** para extração e análise, onde empatou com os outros por uma fração do custo.

Isso já está aplicado com a variável `ANTHROPIC_MODELS` (ver `.env.example`). A geração de textos também foi para o Sonnet, por decisão de custo: a avaliação ainda não mede a qualidade da escrita. Só a extração do perfil continua no `ANTHROPIC_MODEL` (Opus): ela roda uma vez por currículo e alimenta todo o resto. Uma rodada só e 7 invenções plantadas ainda são pouco para cravar. Vale revisar o gabarito, aumentar os textos plantados e rodar de novo com a combinação.

## Antes e depois

Ao mudar um prompt, rode de novo com um `--label` que descreva a mudança (ex.: `--label "extract_job v2"`). A tabela em `results.md` mostra as rodadas lado a lado.
