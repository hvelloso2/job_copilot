# job-copilot

Assistente pessoal de candidaturas a vagas: lê o seu currículo, extrai os requisitos das vagas, analisa a compatibilidade e gera textos para processos seletivos usando a API da Anthropic (Claude). A IA não pode inventar experiência ou skill: tudo o que ela gera é conferido contra o seu perfil.

> **Status:** em desenvolvimento. A base do backend (Etapa 1), o perfil a partir do currículo (Etapa 2) e a extração de vagas (Etapa 3) estão prontos. As funcionalidades de IA ainda estão sendo implementadas, conforme o roteiro abaixo.

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
| 4. Análise | Requisito por requisito: atende, parcial ou não atende, com evidência verificada em código | ⏳ |
| 5. Textos | Resumo, carta e respostas, com espaços `[PREENCHER]` em vez de inventar | ⏳ |
| 6. Interface | React + kanban das candidaturas | ⏳ |
| 7. Painel | Skills mais pedidas e lacunas do perfil | ⏳ |
| 8. Avaliação | Métricas de qualidade e custo da IA | ⏳ |

**Stack:** Python, FastAPI, SQLAlchemy + SQLite, SDK `anthropic`, pypdf, pytest. Frontend (a partir da Etapa 6): React, TypeScript, Vite, TailwindCSS, shadcn/ui, Zustand e dnd-kit.

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
   - usa sempre o modelo configurado;
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
- [Node.js 20+](https://nodejs.org/) (só a partir da Etapa 6, para o frontend)
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
| `ANTHROPIC_FALLBACKS` | `default` liga o fallback em caso de recusa; vazio desliga | `default` |
| `DATABASE_URL` | Onde fica o banco SQLite | `sqlite:///../data/job_copilot.db` |

### 5. Rodar o servidor

Com o ambiente virtual ativado, dentro de `backend/`:

```bash
uvicorn app.main:app --reload
```

Abra no navegador:

- http://localhost:8000/health → deve responder `{"status": "ok"}`
- http://localhost:8000/docs → documentação interativa da API

### 6. Rodar os testes

```bash
pytest
```

Os testes não precisam de chave de API: usam banco em memória e Claude mockado.

### 7. Usar: criar o seu perfil

1. Abra http://localhost:8000/docs.
2. Em `POST /profile/upload`, clique em **Try it out**, escolha o PDF do currículo e execute. A resposta traz o perfil extraído (`data`) e o texto lido do PDF (`raw_text`).
3. Revise o `data`: corrija o que estiver errado e apague o que não for verdade.
4. Em `PUT /profile`, envie `{"data": <perfil revisado>, "raw_text": <texto>}` para salvar.
5. `GET /profile` mostra o perfil salvo e a versão atual.

> Até a interface ficar pronta (Etapa 6), a revisão é feita por essa página de documentação.

### 8. Usar: cadastrar uma vaga

1. Em http://localhost:8000/docs, abra `POST /jobs` e envie `{"text": "<texto da vaga colado>", "url": "<link opcional>"}`.
2. Confira na resposta se os requisitos (`required_requirements` e `preferred_requirements`) saíram separados e corretos.
3. Se a vaga tiver várias trilhas (`needs_track_choice: true`), escolha uma em `PUT /jobs/{id}/track` com `{"track": <índice>}` (a primeira é `0`).
4. `GET /jobs` lista as vagas; `GET /jobs?status=saved` filtra pelo status da candidatura.

### Problemas comuns

- **`ModuleNotFoundError`:** o ambiente virtual não está ativado ou você não está dentro de `backend/`.
- **`ANTHROPIC_MODEL is not set`:** falta preencher o `backend/.env`.
- **Porta 8000 ocupada:** use `uvicorn app.main:app --reload --port 8001`.

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
│   │   ├── routers/         # endpoints (profile, jobs)
│   │   └── llm/
│   │       ├── client.py    # cliente do Claude (saída estruturada, tokens e tempo)
│   │       ├── schemas.py   # schemas Pydantic das respostas da IA
│   │       └── prompts/     # prompts em arquivos próprios
│   ├── tests/               # testes (pytest)
│   ├── requirements.txt
│   └── .env.example
├── data/                    # banco local e uploads (fora do Git)
├── CLAUDE.md                # regras do projeto para o Claude Code
└── README.md
```
