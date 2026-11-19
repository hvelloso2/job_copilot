# job-copilot

Assistente pessoal de candidaturas a vagas: lê o seu currículo, extrai os requisitos das vagas, analisa a compatibilidade e gera textos para processos seletivos usando a API da Anthropic (Claude). A IA não pode inventar experiência ou skill: tudo o que ela gera é conferido contra o seu perfil.

> **Status:** todas as etapas do roteiro estão prontas: perfil, vagas, análise, textos, interface, painel, avaliação da IA, alertas por e-mail e extensão do navegador.

---

## Sumário

- [Como o sistema funciona](#como-o-sistema-funciona)
- [Roteiro do projeto](#roteiro-do-projeto)
- [Como foi implementado (passo a passo)](#como-foi-implementado-passo-a-passo)
- [Regras de uso](#regras-de-uso)
- [Como rodar na sua máquina](#como-rodar-na-sua-máquina)
- [Como usar (passo a passo)](#como-usar-passo-a-passo)
- [Problemas comuns](#problemas-comuns)
- [Estrutura de pastas](#estrutura-de-pastas)

---

## Como o sistema funciona

O job-copilot roda **no seu computador** e tem três partes:

| Parte | Onde roda | O que faz |
|---|---|---|
| **Backend** (FastAPI) | terminal 1, `http://localhost:8000` | Guarda tudo no banco local (`data/`), chama a API do Claude e lê o seu e-mail |
| **Interface** (React) | terminal 2, `http://localhost:5173` | As telas que você usa no navegador |
| **Extensão do navegador** | Chrome ou Edge | Botão que envia a vaga aberta na aba para o backend |

O caminho de uma vaga, do começo ao fim:

```
1. Seu perfil          currículo em PDF → perfil revisado por você (base de tudo)
        │
2. A vaga entra        a) você cola o texto em "Nova vaga"
   (3 jeitos)          b) você abre a vaga no site e clica na extensão
                       c) o e-mail de alerta avisa → você abre a vaga → clica na extensão
        │
3. Extração            o Claude separa empresa, cargo e requisitos → card na coluna "Salva"
        │
4. Análise             cada requisito é comparado com o seu perfil → nota de compatibilidade
        │
5. Textos              resumo, carta, respostas → conferidos contra o seu perfil
        │
6. Acompanhamento      você arrasta o card: aplicada → teste → entrevista → oferta
```

O que é bom saber antes de usar:

- **A candidatura é sempre sua.** O app não se candidata e não envia nada para empresas. Ele organiza, analisa e escreve rascunhos.
- **Não há busca automática em sites de vagas.** LinkedIn, Indeed, Catho e Gupy não permitem que programas leiam as vagas sozinhos. Por isso as vagas entram pelos e-mails de alerta que os próprios sites te mandam e pela extensão, que lê só a página que você já está vendo.
- **O e-mail de alerta só avisa.** Ele traz título, empresa, local e link. O texto completo da vaga vem quando você abre o link e clica na extensão.
- **O que custa dinheiro** são as chamadas ao Claude: ler o currículo, extrair cada vaga, analisar, gerar texto e ler cada e-mail de alerta novo. Ver o quadro, mover cards e abrir vagas não custa nada.

---

## Roteiro do projeto

| Etapa | O que entrega | Status |
|---|---|---|
| 1. Base do backend | API FastAPI, banco SQLite, cliente do Claude | ✅ Pronta |
| 2. Perfil | Upload do currículo em PDF → perfil estruturado, revisado pelo usuário | ✅ Pronta |
| 3. Vagas | Texto da vaga → empresa, cargo, requisitos, stack, senioridade | ✅ Pronta |
| 4. Análise | Requisito por requisito: atende, parcial ou não atende, com evidência verificada em código | ✅ Pronta |
| 5. Textos | Resumo, carta e respostas, com espaços `[PREENCHER]` em vez de inventar | ✅ Pronta |
| 6. Interface | React + kanban das candidaturas | ✅ Pronta |
| 7. Painel | Skills mais pedidas e lacunas do perfil | ✅ Pronta |
| 8. Avaliação | Métricas de qualidade e custo da IA | ✅ Pronta |
| Alertas e extensão | Vagas dos e-mails de alerta (LinkedIn, Gupy, Indeed...) e botão no navegador que envia a vaga aberta para o quadro | ✅ Pronta |

**Stack:** backend em Python, FastAPI, SQLAlchemy + SQLite, SDK `anthropic`, pypdf e pytest. Frontend em React, TypeScript, Vite, TailwindCSS, shadcn/ui, Zustand, dnd-kit e Vitest.

---

## Como foi implementado (passo a passo)

Esta seção descreve só o que já existe no código e é atualizada a cada etapa.

### Etapa 0: preparação do repositório

1. **`.gitignore`** criado antes de qualquer código, para que dados pessoais nunca sejam commitados: `.env` (chave da API), `data/` (banco e currículo), ambientes virtuais e `node_modules`.
2. **`CLAUDE.md`** na raiz com as regras do projeto (stack, estrutura e a regra principal de não inventar informações), usado como contexto pelo Claude Code durante o desenvolvimento.

### Etapa 1: base do backend

1. **Configuração por variáveis de ambiente** ([backend/app/config.py](backend/app/config.py)): `pydantic-settings` lê o `backend/.env`. O modelo do Claude vem de `ANTHROPIC_MODEL` e nunca fica fixo no código, para poder trocar de modelo sem mexer no código.
2. **Banco de dados** ([backend/app/database.py](backend/app/database.py)): SQLite via SQLAlchemy 2.0. O arquivo do banco fica em `data/job_copilot.db` e a pasta é criada automaticamente. As tabelas são criadas quando o servidor sobe.
3. **Modelos** ([backend/app/models.py](backend/app/models.py)):
   - `Profile`: perfil estruturado (JSON), texto original do currículo, versão e data de atualização.
   - `Job`: empresa, cargo, texto original da vaga, dados extraídos (JSON), link opcional.
   - `Application`: status da candidatura (`saved`, `applied`, `test`, `interview`, `offer`, `closed`), histórico com a data de cada mudança de status e notas.
   - `Analysis`: resultado da análise de uma vaga e a versão do perfil usada nela.
   - `GeneratedText`: textos gerados por vaga (resumo, carta ou resposta).
   - Ao apagar uma vaga, a candidatura, as análises e os textos dela são apagados junto.
4. **Cliente do Claude** ([backend/app/llm/client.py](backend/app/llm/client.py)): uma camada fina sobre o SDK oficial `anthropic` que:
   - usa sempre o modelo configurado, que pode ser diferente por operação (`ANTHROPIC_MODELS`, escolhido com base na avaliação da Etapa 8);
   - registra tokens de entrada e saída e o tempo de cada chamada, base para medir o custo depois;
   - pode receber um SDK falso, para que os testes nunca chamem a API real;
   - opcionalmente liga o *fallback* do servidor (`ANTHROPIC_FALLBACKS=default`): se o modelo recusar um pedido, a API refaz o pedido em outro modelo.
5. **API** ([backend/app/main.py](backend/app/main.py)): FastAPI com `GET /health`.
6. **Testes** ([backend/tests/](backend/tests/)): banco em memória e Claude mockado. Cobrem o `/health`, a persistência dos modelos, o histórico de status, a exclusão em cascata e o registro de uso do cliente do Claude.

### Etapa 2: perfil a partir do currículo

1. **Schema do perfil** ([backend/app/llm/schemas.py](backend/app/llm/schemas.py)): o modelo Pydantic `ProfileData` define resumo, experiências (cargo, empresa, período, atividades), skills por categoria, projetos, formação, certificações e idiomas. Campos ausentes no currículo ficam `null` ou como lista vazia, para que o modelo não seja obrigado a inventar um valor.
2. **Saída estruturada com validação em código** ([backend/app/llm/client.py](backend/app/llm/client.py)): o método `create_structured` gera o JSON Schema a partir do modelo Pydantic e o envia em `output_config.format`, o que restringe a resposta do Claude a esse formato. A resposta é validada de novo com Pydantic. Recusa do modelo, resposta cortada por limite de tokens, JSON inválido ou campos fora do schema viram um erro claro (`LLMOutputError`), e nada inválido chega ao banco.
3. **Prompt em arquivo próprio** ([backend/app/llm/prompts/extract_profile.md](backend/app/llm/prompts/extract_profile.md)): proíbe deduzir, completar ou enfeitar informações. Por exemplo, não adiciona "Git" só porque a pessoa usou GitHub. Também não extrai dados de contato.
4. **Leitura do PDF** ([backend/app/pdf.py](backend/app/pdf.py)): extrai o texto com pypdf. Um PDF sem texto selecionável (currículo escaneado) ou corrompido gera uma mensagem de erro explicando o motivo.
5. **Endpoints** ([backend/app/routers/profile.py](backend/app/routers/profile.py)):
   - `POST /profile/upload`: recebe o PDF (até 5 MB) e devolve o perfil extraído e o texto original **sem salvar**.
   - `PUT /profile`: salva o perfil depois que o usuário revisa. Cada vez que salva, a versão sobe (as análises das próximas etapas registram qual versão usaram).
   - `GET /profile`: devolve o perfil atual.
6. **Testes**: upload com sucesso sem salvar nada, resposta inválida do modelo (JSON quebrado, fora do schema, cortada, recusa), arquivo que não é PDF, PDF sem texto, versionamento no `PUT` e rejeição de perfil inválido.

### Etapa 3: extração de vagas

1. **Schema da vaga** ([backend/app/llm/schemas.py](backend/app/llm/schemas.py)): `JobData` tem empresa, cargo, senioridade, modalidade (`remote`, `hybrid` ou `onsite`), local, requisitos obrigatórios, requisitos desejáveis, tecnologias, responsabilidades, benefícios e salário. O Claude devolve um `JobExtraction` com uma lista de **trilhas**: uma vaga comum tem uma trilha só; uma vaga que oferece vários perfis (por exemplo "AI Engineer" e "AI Builder") tem uma trilha para cada, com seus próprios requisitos.
2. **Prompt** ([backend/app/llm/prompts/extract_job.md](backend/app/llm/prompts/extract_job.md)): um requisito por item, curto, separando itens compostos ("Python e Django" vira dois). Mantém números como estão escritos e não deduz senioridade, modalidade ou tecnologias que a vaga não cita.
3. **Limpeza em código**: as listas são normalizadas depois da validação (espaços extras, itens vazios e duplicados removidos). Uma resposta sem nenhuma trilha ou com modalidade fora das três opções é rejeitada.
4. **Endpoints** ([backend/app/routers/jobs.py](backend/app/routers/jobs.py)):
   - `POST /jobs`: recebe o texto colado da vaga e um link opcional (só guardado), extrai com o Claude e salva a vaga junto com a candidatura no status `saved` (salva).
   - `GET /jobs`: lista as vagas, da mais recente para a mais antiga, com filtro opcional `?status=`.
   - `GET /jobs/{id}`: vaga completa, com o texto original, as trilhas e o histórico de status.
   - `PUT /jobs/{id}/track`: escolhe qual trilha acompanhar quando a vaga tem mais de uma. Com uma trilha só, ela já vem escolhida; com várias, a vaga fica marcada com `needs_track_choice: true` até a escolha.
5. **Erros da IA** ([backend/app/dependencies.py](backend/app/dependencies.py)): a tradução de erros do Claude (resposta inválida, falha de conexão, erro da API) em respostas HTTP agora fica num só lugar, usada pelo perfil e pelas vagas.
6. **Testes**: criação com candidatura em `saved`, limpeza dos requisitos, vaga com duas trilhas e escolha da trilha, trilha inexistente, resposta inválida do modelo (nada é salvo), resposta sem trilhas, modalidade inválida, texto vazio (o Claude nem é chamado), filtro por status e vaga inexistente.

### Etapa 4: análise de compatibilidade com verificação

1. **O que vai para o Claude** ([backend/app/routers/analysis.py](backend/app/routers/analysis.py)): o perfil salvo (o revisado, não o texto bruto do currículo) e os requisitos da trilha escolhida, cada um com um id (`R1`, `R2`... obrigatórios; `P1`... desejáveis). O texto dos requisitos vem do banco, não da resposta do modelo, então o modelo não consegue alterar um requisito.
2. **O que o Claude devolve** ([backend/app/llm/schemas.py](backend/app/llm/schemas.py), prompt em [analyze_job.md](backend/app/llm/prompts/analyze_job.md)): para cada requisito, o status (`meets`, `partial`, `missing`), um trecho **copiado literalmente** do perfil como evidência e uma explicação curta. Também devolve pontos fortes (cada um com evidência), lacunas, sugestões de ajuste no currículo e o que estudar. No schema, a evidência e a explicação vêm antes do status, para o modelo justificar antes de decidir.
3. **Verificação em código** ([backend/app/analysis.py](backend/app/analysis.py)). O código não confia na resposta do modelo:
   - **Evidência:** precisa existir dentro de um mesmo campo do perfil (ignorando maiúsculas, espaços e tipo de aspas). Se não existir, o requisito é rebaixado para `missing` com a nota "Evidência não encontrada no perfil". O status original do modelo fica guardado em `model_status`, para auditoria e para a avaliação da Etapa 8.
   - **Requisito "atendido" sem evidência:** também vira `missing`. Um requisito que o modelo esqueceu de avaliar entra como `missing` com uma nota.
   - **Pontos fortes:** cada um é marcado como verificado ou não, com a mesma regra.
   - **Sugestões de currículo:** o trecho `original` precisa existir no perfil. O texto sugerido é varrido em busca de skills (as que o modelo declarou e as tecnologias da vaga que aparecem no texto) e de números que não estão no perfil. Tudo o que for encontrado aparece em `unsupported`.
   - Evidências e skills são buscadas por palavra inteira: "Java" não é encontrado em "JavaScript", nem "Git" em "GitHub".
   - A data de hoje vai junto no pedido, para o modelo ler períodos como "2023 - atual" e não tratar como futura uma data que já passou.
4. **Nota em código:** obrigatório pesa 2 e desejável pesa 1; `meets` vale 1, `partial` vale 0,5 e `missing` vale 0. A nota (0 a 100) é a média ponderada dos status **já verificados**. O modelo não dá nota.
5. **Histórico:** cada análise é salva com a versão do perfil usada. Se você editar o perfil depois, a análise aparece com `outdated: true`.
6. **Endpoints:** `POST /jobs/{id}/analysis` (analisa e salva) e `GET /jobs/{id}/analysis` (análise mais recente). A análise exige um perfil salvo e uma trilha escolhida.
7. **Testes:** um modelo mockado que inventa evidências é pego, e a nota volta a ser a mesma de uma resposta honesta. Também cobrem: evidência parafraseada, trechos de campos diferentes juntados com "...", "atende" sem evidência, ids duplicados, desconhecidos ou faltando, pontos fortes inventados, sugestões com skill ou número inventado, pesos da nota, versão do perfil e análise desatualizada.

### Etapa 5: textos para o processo seletivo

1. **Tipos de texto** ([backend/app/routers/texts.py](backend/app/routers/texts.py)): `summary` (resumo adaptado para o currículo), `cover_letter` (carta de apresentação curta) e `answer` (resposta a uma pergunta do processo seletivo). A resposta pode ser `written` (texto escrito) ou `audio_script` (roteiro para ler em voz alta em cerca de 1 minuto).
2. **Contexto da geração** (prompt em [generate_text.md](backend/app/llm/prompts/generate_text.md)): o perfil salvo, a vaga e **só a parte verificada** da análise mais recente. Evidências rejeitadas na Etapa 4 não chegam ao modelo. Por isso é preciso analisar a vaga antes de gerar textos.
3. **`[PREENCHER: ...]`**: quando o texto precisa de algo que não está no perfil (um resultado concreto, o motivo de querer a empresa, o seu nome), o modelo deixa um espaço marcado em vez de inventar. A API devolve a lista do que falta em `placeholders`.
4. **Segunda verificação** ([backend/app/texts.py](backend/app/texts.py), prompt em [extract_claims.md](backend/app/llm/prompts/extract_claims.md)): uma segunda chamada ao Claude lista cada afirmação sobre você que aparece no texto, com a evidência no perfil. O código decide o que tem suporte, com as mesmas regras da análise:
   - a evidência precisa existir no perfil;
   - skills e números dentro da afirmação precisam estar no perfil (por exemplo, "3 anos de Python" é marcado se o perfil não tem "3");
   - afirmações sem suporte voltam destacadas em `highlighted_text` como `[[SEM SUPORTE: ...]]`, com a posição no texto e o motivo.
5. **Rede de segurança**: o código também varre o texto inteiro (fora dos `[PREENCHER]`) atrás de skills da vaga e números que não estão no perfil. Isso pega afirmações que o modelo "esqueceu" de listar, e elas aparecem em `warnings`.
6. **Histórico**: cada texto é salvo com a verificação, a versão do perfil e a análise usadas. `GET /jobs/{id}/texts` lista do mais recente para o mais antigo.
7. **Migração simples do banco** ([backend/app/database.py](backend/app/database.py)): ao subir, o servidor adiciona ao banco local as colunas novas que ainda não existem. Assim um banco criado nas etapas anteriores continua funcionando.
8. **Testes**: afirmações inventadas (número, skill, evidência falsa ou ausente) são pegas; afirmações dentro de `[PREENCHER]` e duplicadas são ignoradas; termos que o modelo não listou aparecem nos avisos; o prompt de geração não recebe as evidências rejeitadas; pedidos inválidos são recusados sem chamar o Claude; nada é salvo se a auditoria falhar; e a migração de um banco antigo funciona.

### Etapa 6: interface

1. **Projeto** ([frontend/](frontend/)): React + TypeScript com Vite, TailwindCSS e componentes do shadcn/ui. Em desenvolvimento, o Vite encaminha as chamadas `/api/...` para o backend em `localhost:8000` (proxy), então não é preciso configurar CORS.
2. **Candidaturas** ([frontend/src/pages/BoardPage.tsx](frontend/src/pages/BoardPage.tsx)): kanban com as colunas salva, aplicada, teste, entrevista, oferta e encerrada. Os cards são arrastados com dnd-kit. Cada card mostra empresa, cargo, nota de compatibilidade (verde, amarelo ou vermelho), há quantos dias a candidatura foi atualizada e um aviso se falta escolher a trilha. O estado do quadro fica num store do Zustand ([frontend/src/stores/jobsStore.ts](frontend/src/stores/jobsStore.ts)): o card muda de coluna na hora e volta para a coluna anterior se o servidor recusar.
3. **Nova vaga** ([frontend/src/components/board/NewJobDialog.tsx](frontend/src/components/board/NewJobDialog.tsx)): você cola o texto, o Claude extrai e a tela mostra requisitos, tecnologias, senioridade e modalidade para conferir. Dá para confirmar, escolher a trilha (quando há várias) ou descartar.
4. **Página da vaga** ([frontend/src/pages/JobPage.tsx](frontend/src/pages/JobPage.tsx)), com quatro abas:
   - **Análise:** a nota, os requisitos com status coloridos e a evidência. Os requisitos rebaixados pelo verificador aparecem em vermelho, com o que o modelo tinha dito. Também mostra pontos fortes, lacunas, sugestões de currículo (as que trazem algo fora do perfil ficam marcadas) e o que estudar. Avisa quando o perfil mudou depois da análise.
   - **Textos:** gerador de resumo, carta e resposta (texto escrito ou roteiro para áudio). As afirmações sem suporte aparecem sublinhadas em vermelho (passando o mouse, aparece o motivo), e os `[PREENCHER]` em amarelo. Tem botão de copiar e histórico dos textos gerados.
   - **Vaga:** os dados extraídos e o texto original.
   - **Notas:** campo de notas e histórico de status com datas.
5. **Perfil** ([frontend/src/pages/ProfilePage.tsx](frontend/src/pages/ProfilePage.tsx)): upload do PDF, revisão e edição de todas as seções (experiências, skills, projetos, formação, certificações e idiomas) e botão salvar. O perfil extraído só é gravado quando você clica em **Salvar perfil**. Listas como atividades e skills são editadas com um item por linha, porque vários itens têm vírgula (por exemplo, "scikit-learn (Regressão Linear, Random Forest)").
6. **Carregamento e erros:** toda chamada ao Claude mostra o que está acontecendo ("Comparando seu perfil com a vaga..."), e os erros do backend aparecem com a mensagem dele, em português. Se o backend estiver desligado, a tela diz isso.
7. **Backend:** endpoints novos para a interface: `PATCH /jobs/{id}/application` (muda o status ou as notas), `DELETE /jobs/{id}` (apaga a vaga com a análise e os textos), e a lista de vagas passou a trazer a nota da última análise e a data de atualização.
8. **Testes (Vitest):** destaque do texto, datas (o backend grava em UTC), mensagens de erro da API, store do kanban (mudança na hora e volta em caso de erro) e componentes (destaque em vermelho e amarelo, campo "um item por linha"). No backend, testes para os endpoints novos.

### Alertas por e-mail e extensão do navegador

Os grandes sites de vagas (LinkedIn, Indeed, Catho, Gupy) não permitem leitura automática: proíbem no `robots.txt`, recusam a conexão ou só mostram as vagas com JavaScript. Por isso o app não raspa sites. As vagas chegam por dois caminhos legítimos: os e-mails de alerta que os próprios sites te mandam e a página que você já está vendo no navegador.

1. **Extensão do navegador** ([extension/](extension/)): um botão na barra do Chrome (ou Edge) que envia a vaga aberta para o job-copilot.
   - Só age quando você clica, e só lê a aba atual. Funciona em qualquer site, inclusive com login, porque é você navegando.
   - Envia o texto selecionado, se houver. Se não houver, envia a área da descrição da vaga (no LinkedIn) ou a página inteira.
   - O backend recebe em `POST /jobs/import`, extrai a vaga como se tivesse sido colada e abre a página da vaga no app.
   - A mesma vaga não é extraída duas vezes. O endereço é padronizado ([backend/app/job_urls.py](backend/app/job_urls.py)): tira os parâmetros de rastreio, e no LinkedIn `/jobs/search/?currentJobId=123` e `/comm/jobs/view/123` viram `/jobs/view/123/`.
2. **E-mails de alerta** ([backend/app/alerts/](backend/app/alerts/)): na página **Alertas**, o botão **Ler e-mails de alerta**:
   - Lê a sua caixa por IMAP ([mailbox.py](backend/app/alerts/mailbox.py)), só os remetentes de `ALERT_SENDERS` e dos últimos `ALERT_DAYS` dias.
   - É só leitura: nada é marcado como lido, movido ou apagado.
   - Cada e-mail é lido uma vez só (tabela `alert_emails`), no máximo `ALERT_MAX_EMAILS` por vez.
   - O Claude (Haiku, operação `read_job_alert`) lista as vagas de cada e-mail ([reader.py](backend/app/alerts/reader.py)):
     - O e-mail vai como texto com os links numerados ("Desenvolvedor Python [3]"), e o Claude responde só com o número do link. Assim, todo endereço vem do próprio e-mail.
     - Título, empresa e local só são guardados se estiverem escritos no e-mail. O que o modelo inventar é descartado.
   - As vagas ficam na tabela `job_leads`, nas abas **Novas**, **Importadas** e **Descartadas**. O e-mail traz só título, empresa, local e link: para ter o texto completo, abra o link e clique na extensão. A vaga passa sozinha para **Importadas**, com link para o quadro.
   - Uma vaga que aparece em vários e-mails entra uma vez só.
   - Uma vaga que já está no quadro entra direto como importada.
   - Um e-mail com erro não é marcado como lido e é tentado de novo na próxima vez.
3. **Refatoração:** a extração e a análise saíram das rotas para [backend/app/pipeline.py](backend/app/pipeline.py).

---

## Regras de uso

1. **A IA nunca inventa.** Nenhuma experiência, skill ou número sobre você pode aparecer num texto gerado se não estiver no seu perfil salvo. Essa checagem é feita em código, não só pedida no prompt. Quando falta informação, o texto traz `[PREENCHER: ...]` para você completar.
2. **Você revisa antes de salvar.** O perfil extraído do currículo só é gravado depois da sua confirmação.
3. **Uso local, um usuário só.** O app roda na sua máquina e não tem login nem servidor público.
4. **Privacidade.** Seu currículo e suas candidaturas ficam em `data/`, que está no `.gitignore`. O texto do currículo e das vagas é enviado à API da Anthropic para processamento. Para demonstrações ou repositórios públicos, use um **perfil fictício**, nunca o seu currículo real.
5. **Custo.** A API da Anthropic é paga por uso. **Defina um limite de gasto** no [Console da Anthropic](https://console.anthropic.com) antes de começar.
6. **Segredos.** A chave da API, o seu e-mail e a senha de app ficam apenas em `backend/.env`, que não vai para o GitHub. Nunca coloque esses dados no código nem no `.env.example`, que é público.
7. **Revise o que for enviar.** Os textos gerados são rascunhos. Leia e ajuste antes de mandar para uma empresa.

---

## Como rodar na sua máquina

### 1. Pré-requisitos

- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [Node.js 20+](https://nodejs.org/) (para a interface)
- Uma chave de API da Anthropic: crie em [console.anthropic.com](https://console.anthropic.com) e defina um limite de gasto

Para conferir as versões:

```bash
python --version
git --version
```

### 2. Clonar o repositório

```bash
git clone https://github.com/hvelloso2/job-copilot.git
cd job-copilot/backend
```

### 3. Criar o ambiente virtual e instalar as dependências

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Se o PowerShell bloquear a ativação, rode uma vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configurar o `.env`

Na pasta `backend/` existem dois arquivos parecidos. Não confunda:

| Arquivo | Para que serve | Vai para o GitHub? |
|---|---|---|
| `.env.example` | **Modelo** com os nomes das variáveis, sem nenhum valor pessoal. O app **não lê** este arquivo. | Sim. Por isso nunca coloque senha ou e-mail nele. |
| `.env` | **As suas configurações de verdade**: chave da API, e-mail, senhas. É este que o app lê. | Não (está no `.gitignore`). |

Crie o seu `.env` copiando o modelo:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# Linux / macOS
cp .env.example .env
```

Abra o **`backend/.env`** (não o `.env.example`) e preencha. Para começar, só as duas primeiras linhas são obrigatórias; as de e-mail são explicadas em [Alertas por e-mail](#4-alertas-por-e-mail).

| Variável | O que é | Exemplo |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sua chave da API | `sk-ant-...` |
| `ANTHROPIC_MODEL` | Modelo do Claude usado | `claude-opus-5-5` |
| `ANTHROPIC_MODELS` | Opcional: modelo por operação; as que não aparecem usam `ANTHROPIC_MODEL` | `extract_job=claude-haiku-5-5,read_job_alert=claude-haiku-5-5,analyze_job=claude-haiku-5-5,generate_text=claude-sonnet-5-5,extract_claims=claude-sonnet-5-5` |
| `ANTHROPIC_FALLBACKS` | `default` liga o fallback em caso de recusa; vazio desliga | `default` |
| `DATABASE_URL` | Onde fica o banco SQLite | `sqlite:///../data/job_copilot.db` |
| `IMAP_HOST` | Opcional, para os alertas: o **servidor** de e-mail (não é o seu e-mail) | `imap.gmail.com` |
| `IMAP_USER` | O **seu endereço** de e-mail | `voce@gmail.com` |
| `IMAP_PASSWORD` | Uma **senha de app** do Google, nunca a senha da conta | `abcd efgh ijkl mnop` |
| `IMAP_FOLDER` | Pasta lida | `INBOX` |
| `ALERT_SENDERS` | Domínios dos remetentes de alerta lidos | `linkedin.com,indeed.com,gupy.io,...` |
| `ALERT_DAYS` / `ALERT_MAX_EMAILS` | Quantos dias para trás e quantos e-mails novos por leitura | `14` / `20` |

### 5. Rodar o servidor

Com o ambiente virtual ativado, dentro de `backend/`:

```bash
python -m uvicorn app.main:app --reload
```

Abra no navegador:

- http://localhost:8000/health → deve responder `{"status": "ok"}`
- http://localhost:8000/docs → documentação interativa da API

### 6. Rodar a interface

Em **outro terminal**, com o backend rodando:

```bash
cd frontend
npm install   # só na primeira vez
npm run dev
```

Abra http://localhost:5173.

> **Toda vez que mudar o `backend/.env`, reinicie o backend** (Ctrl+C no terminal dele e rode o `uvicorn` de novo). O `.env` só é lido quando o servidor começa.

### 7. Instalar a extensão do navegador

1. No Chrome, abra `chrome://extensions` (no Edge, `edge://extensions`) e ligue o **Modo do desenvolvedor**.
2. Clique em **Carregar sem compactação** e escolha a pasta `extension/` do projeto.
3. Fixe o ícone do job-copilot na barra (ícone de quebra-cabeça › alfinete).

A extensão envia para `http://localhost:8000` e abre `http://localhost:5173`. Se usar outras portas, mude `API_URL` e `APP_URL` em [extension/background.js](extension/background.js) e a permissão em [extension/manifest.json](extension/manifest.json), e clique em recarregar na página de extensões.

### 8. Rodar os testes

```bash
# backend (dentro de backend/, com o ambiente virtual ativado)
python -m pytest

# frontend (dentro de frontend/)
npm test
```

Os testes não precisam de chave de API: o backend usa banco em memória e Claude mockado, e o frontend simula as respostas da API.

---

## Como usar (passo a passo)

Antes, deixe rodando o backend (terminal 1) e a interface (terminal 2), como em [Como rodar na sua máquina](#como-rodar-na-sua-máquina).

### 1. Cadastre o seu perfil (uma vez)

1. Abra http://localhost:5173 e clique em **Perfil**.
2. Envie o PDF do currículo. O Claude monta um rascunho com experiências, skills, projetos e formação.
3. **Revise com cuidado:** corrija o que saiu errado e apague o que não for verdade. Tudo o que ficar aqui pode ser usado nas análises e nos textos.
4. Clique em **Salvar perfil**.

Quando o currículo mudar, envie o PDF novo e salve de novo.

### 2. Adicione vagas

Há três jeitos. Todos levam a vaga para a coluna **Salva** do quadro **Candidaturas**.

**a) Colando o texto**

1. Em **Candidaturas**, clique em **Nova vaga**.
2. Cole o texto inteiro da vaga e, se quiser, o link.
3. Confira se os requisitos saíram separados e corretos. Se a vaga tiver várias trilhas (ex.: "Backend" e "Frontend"), escolha uma.

**b) Pela extensão do navegador** (precisa da extensão instalada, passo 7 da instalação)

1. Abra a vaga no site (LinkedIn, Gupy, Indeed, site da empresa...). Pode ser na lista de resultados do LinkedIn, com a vaga aberta do lado.
2. Clique no ícone do job-copilot na barra do navegador.
3. O ícone mostra `…` enquanto a vaga é extraída (alguns segundos) e `OK` quando termina. A página da vaga abre no app.
4. Se a página tiver muita coisa além da vaga, **selecione o texto da vaga** antes de clicar: a extensão envia só o que estiver selecionado.
5. Se a vaga já estiver no quadro, ela não é extraída de novo: o app só abre a que já existe.

**c) Pelos e-mails de alerta:** veja o passo 4.

### 3. Analise e escreva

1. Abra a vaga (clique no cargo, no card).
2. Clique em **Analisar compatibilidade**. Cada requisito aparece como atende, parcial ou não atende, com a evidência do seu perfil. Os marcados com "Evidência não encontrada" foram rebaixados pelo verificador.
3. Na aba **Textos**, gere o resumo, a carta ou a resposta a uma pergunta do processo:
   - o que estiver sublinhado em **vermelho** não foi encontrado no seu perfil: corrija ou apague;
   - o que estiver em **amarelo** (`[PREENCHER: ...]`) é para você completar.
4. Só depois copie e envie para a empresa.
5. Conforme o processo avança, arraste o card (aplicada, teste, entrevista, oferta, encerrada) e anote datas e contatos na aba **Notas**.

### 4. Alertas por e-mail

São **três configurações em lugares diferentes**:

| O quê | Onde | Para quê |
|---|---|---|
| A. Os alertas | **Nos sites de vagas** (LinkedIn, Gupy...) | Os sites te mandam e-mails com vagas novas |
| B. Uma senha de app | **Na sua conta Google** | Permite ao app ler o e-mail sem usar a sua senha |
| C. O acesso ao e-mail | **No arquivo `backend/.env`** | Diz ao app qual e-mail ler |

**A. Crie os alertas nos sites.** Isso não é feito no job-copilot.

- **LinkedIn:**
  1. Abra https://www.linkedin.com/jobs.
  2. Pesquise o cargo (ex.: `desenvolvedor júnior`) e o local (ex.: `Brasil`).
  3. Na página de resultados, ligue a chave **Ativar alerta** (ou **Definir alerta**), no topo da lista.
  4. Em **Vagas › Preferências › Alertas de vagas**, confira se o alerta vai **por e-mail**.
- **Indeed, InfoJobs, Gupy e outros:** depois de pesquisar, procure "Criar alerta", "Receber vagas por e-mail" ou um ícone de sino.
- Crie quantas buscas quiser (ex.: `python júnior`, `estágio desenvolvimento`). Os e-mails chegam normalmente uma vez por dia.

**B. Crie uma senha de app no Google**

O app não usa a senha do seu Gmail. Ele usa uma *senha de app*, que serve só para isso e pode ser apagada a qualquer momento.

1. Em https://myaccount.google.com/security, confira se a **Verificação em duas etapas** está ativada. Sem ela, a senha de app não aparece.
2. Abra https://myaccount.google.com/apppasswords.
3. Dê um nome (ex.: `job-copilot`) e clique em **Criar**.
4. Copie a senha de 16 letras que aparece. Ela só é mostrada uma vez.

Contas de empresa ou escola, e contas com Proteção Avançada, podem não ter essa opção. Nesse caso, use uma conta pessoal.

**C. Coloque no `backend/.env`**

Abra o **`backend/.env`** (não o `.env.example`) e deixe assim, com os seus dados:

```
IMAP_HOST=imap.gmail.com
IMAP_USER=voce@gmail.com
IMAP_PASSWORD=abcdefghijklmnop
```

Cada campo tem o seu lugar:

- `IMAP_HOST` é o endereço do **servidor** do Gmail. Fica sempre `imap.gmail.com`.
- `IMAP_USER` é o **seu e-mail**.
- `IMAP_PASSWORD` é a **senha de app** do passo B, com ou sem espaços.

Salve o arquivo e **reinicie o backend**.

**D. Leia os alertas**

1. Abra a página **Alertas**. No topo deve aparecer `voce@gmail.com / INBOX`. Se aparecer o quadro "Configure o e-mail", o `.env` não foi lido: confira o passo C e reinicie o backend.
2. Clique em **Ler e-mails de alerta**. O app lê os e-mails de alerta dos últimos 14 dias, e cada e-mail só uma vez. Nada é marcado como lido, movido ou apagado na sua caixa.
3. As vagas aparecem na aba **Novas**, com título, empresa, local e link.
4. Para cada vaga:
   - **Interessou:** clique no título para abrir no site e depois no ícone da extensão. A vaga vai para o quadro e passa sozinha para a aba **Importadas**.
   - **Não interessou:** clique em **Descartar**. Dá para desfazer em **Descartadas › Restaurar**.

### Rotina sugerida

1. Uma vez por dia, abra **Alertas** e clique em **Ler e-mails de alerta**.
2. Descarte o que não interessa e envie o resto pela extensão.
3. No quadro, analise as vagas novas e gere os textos das que valerem a candidatura.
4. Candidate-se no site da empresa e arraste o card para **Aplicada**.
5. De vez em quando, olhe o **Painel**: skills mais pedidas nas vagas e as que faltam no seu perfil.

---

## Problemas comuns

**Instalação**

- **`ModuleNotFoundError`:** o ambiente virtual não está ativado ou você não está dentro de `backend/`.
- **`ANTHROPIC_MODEL is not set`:** falta preencher o `backend/.env`.
- **Porta 8000 ocupada:** use `uvicorn app.main:app --reload --port 8001` e rode o frontend apontando para ela (PowerShell: `$env:BACKEND_URL="http://localhost:8001"; npm run dev`). A extensão também precisa da porta nova (veja o passo 7 da instalação).
- **A interface diz que não consegue falar com o servidor:** o backend não está rodando no outro terminal.
- **`npx vitest` no Windows falha com "Vitest failed to find the current suite":** é um problema do Vitest quando a pasta é aberta como `c:\` (minúsculo). Use `npm test`, que já contorna isso.

**Extensão**

- **Aparece "Não consegui falar com o job-copilot":** o backend não está rodando, ou está em outra porta.
- **Aparece "Não encontrei o texto da vaga":** selecione o texto da vaga na página e clique de novo.
- **A vaga veio com requisitos de outras vagas:** a página tinha várias vagas (ex.: a lista do LinkedIn). Apague o card, selecione só o texto da vaga e envie de novo.
- **O ícone não aparece:** confira em `chrome://extensions` se a extensão está ligada e fixe o ícone (quebra-cabeça › alfinete).

**Alertas por e-mail**

- **Continua aparecendo "Configure o e-mail":** o backend não foi reiniciado depois de mudar o `.env`, ou os dados foram colocados no `.env.example` em vez do `.env`.
- **"O servidor recusou o login":**
  - foi usada a senha normal da conta no lugar da senha de app;
  - ou o e-mail foi colocado no `IMAP_HOST` em vez do `IMAP_USER`;
  - ou a senha de app foi apagada. Crie outra.
- **"Nenhum e-mail de alerta novo", mas os alertas chegam:**
  - Os alertas podem estar sendo arquivados por um filtro e não ficam na Caixa de entrada. Use `IMAP_FOLDER=[Gmail]/Todos os e-mails` (`[Gmail]/All Mail` com o Gmail em inglês).
  - O remetente pode não estar em `ALERT_SENDERS`.
  - O e-mail pode ter mais de 14 dias (`ALERT_DAYS`).
  - O e-mail pode já ter sido lido antes: cada e-mail é lido uma vez só.
- **IMAP desligado (contas antigas):** no Gmail, abra ⚙️ › **Ver todas as configurações** › **Encaminhamento e POP/IMAP** › **Ativar IMAP**.
- **Senha de app exposta** (colada num lugar público, num commit ou numa conversa): apague em https://myaccount.google.com/apppasswords e crie outra. Apagar a senha de app não afeta a senha da sua conta.

---

## Estrutura de pastas

```
job-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py          # API FastAPI
│   │   ├── config.py        # configuração via .env
│   │   ├── database.py      # conexão SQLite / SQLAlchemy
│   │   ├── models.py        # tabelas do banco
│   │   ├── schemas.py       # formatos de entrada/saída da API
│   │   ├── pdf.py           # extração de texto do PDF
│   │   ├── analysis.py      # verificação das evidências e nota de compatibilidade
│   │   ├── texts.py         # verificação das afirmações dos textos gerados
│   │   ├── routers/         # endpoints (profile, jobs, analysis, texts, alerts)
│   │   ├── alerts/          # leitura dos e-mails de alerta (IMAP) e das vagas de cada e-mail
│   │   ├── job_urls.py      # endereço padronizado de cada vaga
│   │   └── llm/
│   │       ├── client.py    # cliente do Claude (saída estruturada, tokens e tempo)
│   │       ├── schemas.py   # schemas Pydantic das respostas da IA
│   │       └── prompts/     # prompts em arquivos próprios
│   ├── tests/               # testes (pytest)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/           # Candidaturas (kanban), Vaga, Alertas, Painel e Perfil
│   │   ├── components/      # kanban, nova vaga, análise, textos, notas, editor do perfil
│   │   │   └── ui/          # componentes do shadcn/ui
│   │   ├── stores/          # estado do kanban (Zustand)
│   │   └── lib/             # cliente da API, tipos e formatação
│   ├── scripts/vitest.mjs   # roda o Vitest (contorna o problema da letra do drive no Windows)
│   └── vite.config.ts       # proxy /api para o backend
├── extension/               # extensão do Chrome/Edge que envia a vaga aberta para o app
├── data/                    # banco local e uploads (fora do Git)
├── CLAUDE.md                # regras do projeto para o Claude Code
└── README.md
```
