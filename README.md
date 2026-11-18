# job-copilot

Assistente pessoal de candidaturas a vagas: lê o seu currículo, extrai os requisitos das vagas, analisa a compatibilidade e gera textos para processos seletivos usando a API da Anthropic (Claude). A IA não pode inventar experiência ou skill: tudo o que ela gera é conferido contra o seu perfil.

> **Status:** em desenvolvimento. A base do backend (Etapa 1), o perfil a partir do currículo (Etapa 2), a extração de vagas (Etapa 3), a análise de compatibilidade (Etapa 4), os textos para o processo seletivo (Etapa 5) e a interface (Etapa 6) estão prontos. Faltam o painel de skills e a avaliação da IA, conforme o roteiro abaixo.

---

## Sumário

- [Roteiro do projeto](#roteiro-do-projeto)
- [Como foi implementado (passo a passo)](#como-foi-implementado-passo-a-passo)
- [Regras de uso](#regras-de-uso)
- [Como rodar na sua máquina](#como-rodar-na-sua-máquina)
- [Estrutura de pastas](#estrutura-de-pastas)

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
| 7. Painel | Skills mais pedidas e lacunas do perfil | ⏳ |
| 8. Avaliação | Métricas de qualidade e custo da IA | ⏳ |

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

---

## Regras de uso

1. **A IA nunca inventa.** Nenhuma experiência, skill ou número sobre você pode aparecer num texto gerado se não estiver no seu perfil salvo. Essa checagem é feita em código, não só pedida no prompt. Quando falta informação, o texto traz `[PREENCHER: ...]` para você completar.
2. **Você revisa antes de salvar.** O perfil extraído do currículo só é gravado depois da sua confirmação.
3. **Uso local, um usuário só.** O app roda na sua máquina e não tem login nem servidor público.
4. **Privacidade.** Seu currículo e suas candidaturas ficam em `data/`, que está no `.gitignore`. O texto do currículo e das vagas é enviado à API da Anthropic para processamento. Para demonstrações ou repositórios públicos, use um **perfil fictício**, nunca o seu currículo real.
5. **Custo.** A API da Anthropic é paga por uso. **Defina um limite de gasto** no [Console da Anthropic](https://console.anthropic.com) antes de começar.
6. **Segredos.** A chave da API fica apenas em `backend/.env`. Nunca a coloque no código nem faça commit desse arquivo.
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

Copie o arquivo de exemplo:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env
# Linux / macOS
cp .env.example .env
```

Abra o `backend/.env` e preencha:

| Variável | O que é | Exemplo |
|---|---|---|
| `ANTHROPIC_API_KEY` | Sua chave da API | `sk-ant-...` |
| `ANTHROPIC_MODEL` | Modelo do Claude usado | `claude-opus-5-5` |
| `ANTHROPIC_MODELS` | Opcional: modelo por operação; as que não aparecem usam `ANTHROPIC_MODEL` | `extract_job=claude-haiku-5-5,analyze_job=claude-haiku-5-5,generate_text=claude-sonnet-5-5,extract_claims=claude-sonnet-5-5` |
| `ANTHROPIC_FALLBACKS` | `default` liga o fallback em caso de recusa; vazio desliga | `default` |
| `DATABASE_URL` | Onde fica o banco SQLite | `sqlite:///../data/job_copilot.db` |

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

### 7. Usar o app

1. **Perfil:** envie o PDF do currículo, revise e corrija o que foi extraído e clique em **Salvar perfil**. Apague o que não for verdade: tudo o que ficar aqui pode aparecer nas suas candidaturas.
2. **Nova vaga:** em Candidaturas, clique em **Nova vaga**, cole o texto da vaga e confira se os requisitos saíram separados e corretos. Se a vaga tiver várias trilhas, escolha uma.
3. **Análise:** abra a vaga e clique em **Analisar compatibilidade**. Requisitos marcados em vermelho com "Evidência não encontrada" foram rebaixados pelo verificador.
4. **Textos:** na aba Textos, gere o resumo, a carta ou a resposta a uma pergunta. Corrija o que estiver sublinhado em vermelho, preencha o que estiver em amarelo e só então copie e envie.
5. **Acompanhamento:** arraste o card no kanban conforme o processo avança e use a aba Notas para datas, contatos e próximos passos.

A API também pode ser usada direto pela documentação interativa em http://localhost:8000/docs.

### 8. Rodar os testes

```bash
# backend (dentro de backend/, com o ambiente virtual ativado)
python -m pytest

# frontend (dentro de frontend/)
npm test
```

Os testes não precisam de chave de API: o backend usa banco em memória e Claude mockado, e o frontend simula as respostas da API.

### Problemas comuns

- **`ModuleNotFoundError`:** o ambiente virtual não está ativado ou você não está dentro de `backend/`.
- **`ANTHROPIC_MODEL is not set`:** falta preencher o `backend/.env`.
- **Porta 8000 ocupada:** use `uvicorn app.main:app --reload --port 8001` e rode o frontend apontando para ela (PowerShell: `$env:BACKEND_URL="http://localhost:8001"; npm run dev`).
- **A interface diz que não consegue falar com o servidor:** o backend não está rodando no outro terminal.
- **`npx vitest` no Windows falha com "Vitest failed to find the current suite":** é um problema do Vitest quando a pasta é aberta como `c:\` (minúsculo). Use `npm test`, que já contorna isso.

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
│   │   ├── routers/         # endpoints (profile, jobs, analysis, texts)
│   │   └── llm/
│   │       ├── client.py    # cliente do Claude (saída estruturada, tokens e tempo)
│   │       ├── schemas.py   # schemas Pydantic das respostas da IA
│   │       └── prompts/     # prompts em arquivos próprios
│   ├── tests/               # testes (pytest)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/           # Candidaturas (kanban), Vaga e Perfil
│   │   ├── components/      # kanban, nova vaga, análise, textos, notas, editor do perfil
│   │   │   └── ui/          # componentes do shadcn/ui
│   │   ├── stores/          # estado do kanban (Zustand)
│   │   └── lib/             # cliente da API, tipos e formatação
│   ├── scripts/vitest.mjs   # roda o Vitest (contorna o problema da letra do drive no Windows)
│   └── vite.config.ts       # proxy /api para o backend
├── data/                    # banco local e uploads (fora do Git)
├── CLAUDE.md                # regras do projeto para o Claude Code
└── README.md
```
