# job-copilot

Assistente pessoal de candidaturas a vagas. Uso local, um usuário só.

## Stack
- Backend: Python 3.11+, FastAPI, SQLite via SQLAlchemy, SDK oficial `anthropic`, pypdf
- Frontend: React + TypeScript + Vite + TailwindCSS + shadcn/ui + Zustand
- Testes: pytest (backend), Vitest (frontend)

## Estrutura
- backend/app/          API
- backend/app/llm/      chamadas ao Claude, prompts e schemas
- backend/tests/        testes
- backend/evals/        avaliação da IA
- frontend/             interface
- data/                 banco local e uploads (no .gitignore)

## Regras
- O modelo vem da variável ANTHROPIC_MODEL. Nunca fixo no código.
- Segredos em .env, que está no .gitignore. A pasta data/ também nunca é commitada.
- Toda saída do Claude usada pelo sistema é JSON validado por um schema Pydantic.
- REGRA PRINCIPAL: a IA nunca inventa experiência, skill ou número sobre o usuário.
  Todo texto gerado deve ser verificado contra o perfil salvo.
- Prompts ficam em arquivos próprios em backend/app/llm/prompts/, não espalhados no código.
- Os testes não chamam a API real: o cliente do Claude é mockado.
- Código em inglês; interface e README em português.
- Mudanças pequenas e focadas. Explique o que mudou ao final de cada tarefa.
- Progresso das etapas é registrado em PROGRESSO.md (arquivo local, fora do Git).
