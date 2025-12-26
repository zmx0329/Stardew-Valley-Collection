# Repository Guidelines

Contributor guide aligned to the PRD (`memory_bank/design_document.md`) and stack notes (`memory_bank/tech_stack.md`).


## always
- 重要提示：
- 写任何代码前必须完整阅读 memory-bank/@architecture.md（包含完整数据库结构）
- 写任何代码前必须完整阅读 memory-bank/@design-document.md
- 每完成一个重大功能或里程碑后，必须更新 memory-bank/@architecture.md

## Project Structure & Module Organization
- Current docs live in `memory_bank/`; add future specs under `docs/` at repo root when created.
- Frontend (TypeScript + React + Vite) goes in `frontend/` with `src/components/`, `src/pages/`, `src/state/` (Zustand), `src/assets/`, `src/tests/`.
- Backend (Python + FastAPI) goes in `backend/app/` with `routers/`, `services/`, `clients/` (third-party API wrappers), `models/`, `tests/`.
- Shared automation lives in `scripts/`; `.env.example` should exist in each app root.

## Build, Test, and Development Commands
- Frontend: `cd frontend && npm install`, `npm run dev` (Vite dev server), `npm run build` (production bundle), `npm run preview` (serve built assets), `npm run test` (Vitest).
- Backend: `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`, `uvicorn app.main:app --reload` (local API), `pytest` (tests).
- Lint/format: `npm run lint` + `npm run format` (ESLint/Prettier) in `frontend`; `ruff check .` + `black .` in `backend`.

## Coding Style & Naming Conventions
- TypeScript/React: 2-space indent; camelCase variables/functions; PascalCase components; kebab-case files (e.g., `capture-panel.tsx`). Keep state in `src/state/` and avoid globals.
- Python: 4-space indent; snake_case functions/vars; PascalCase classes; type-hint public functions. Keep API clients in `clients/` with retry/rate limit per `tech_stack.md`.
- UI copy and flows should match the Stardew-inspired tone and left/right layout required in the PRD.

## Testing Guidelines
- Frontend: Vitest + React Testing Library; name tests `*.test.tsx` beside components. Cover upload placeholder, object selection, preview/label sync, and save CTA states.
- Backend: pytest under `backend/app/tests/` named `test_*.py`. Mock vision API, LLM, and Supabase; assert fallbacks.
- Favor deterministic fixtures for pixel/label outputs; avoid calling real third-party APIs in CI.

## Commit & Pull Request Guidelines
- Commits: Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`); subject ≤72 chars.
- PRs: short summary, linked issue/task, screenshots or GIFs for UI changes, commands run (build, lint, tests). Call out PRD acceptance criteria touched (single-label rule, immediate preview sync).
- Note deviations or TODOs explicitly.

## Security & Configuration Tips
- Never commit secrets. Load API keys (vision, LLM, Supabase) from `.env`; document required keys in `.env.example`.
- Use sandbox buckets/DB schemas for dev data; avoid production endpoints without approval.
- Centralize credential access through `clients/` to ease rotation and rate limits.
