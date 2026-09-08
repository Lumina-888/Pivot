# Handoff: Pivot Wave 3 after preview/download HTTP

A fresh agent can continue from this file. Canonical project facts live in the repo, not here.

## Resume in 60 seconds

- Workspace: `E:/AI Project/Pivot`, branch `main`. Do not create `../Pivot-Mxx-*` worktrees.
- Repo entry: `AGENTS.md` → `MODULE_SPEC.md` → `PROGRESS.md` → `HANDOFF.md`.
- Previous session finished the **preview/download HTTP** slice and committed leftover mainline-protocol docs.
- Next slice (unless Owner says otherwise): **composition root** (bootable FastAPI, Argon2, swappable storage). Then Next.js proxy for `/api/v1`.

## What the previous conversation did

Completed Wave 3 “预览/下载 HTTP” that was already sketched in the working tree (approved change + tests + partial impl). Tightened `Content-Disposition` quoting, fixed one ruff E501, ran grouped tests, committed, tagged.

Also committed the previously uncommitted MODULE-SPEC-1.1 protocol docs.

Do not re-implement preview/download. Do not treat Fake TestClient HTTP as GATE-P0 verified.

## Commits / tag

| Commit | Summary |
|---|---|
| `ff1626a` | `docs(M00): 改为主线开发 MODULE-SPEC-1.1` |
| `75007e0` | `feat(M02): 增加文档预览与下载 HTTP [FR-RBAC-003, FR-DOC-007, NFR-SEC-015]` |
| `4c69fd9` | `docs(M02): 批准预览/下载 HTTP 并记录测试证据` |

- Tag: `M02-v0.4.0` on `4c69fd9`.
- Tests: `python ops/run_grouped_tests.py --skip-web` → **236 passed, 2 skipped** (Python 3.12.10 / pytest 9.1.1 / ruff 0.16.6 / fastapi 0.141.1).

## Pointers (read these, do not copy)

- Spec: `SPEC.md` §4.2 `FR-RBAC-003`, §4.3 `FR-DOC-007`, §5.3 preview/download, §8.1–8.2, `NFR-SEC-015/016`.
- Contract: `spec/contracts/openapi.yaml` `GET /documents/{id}/preview|download`.
- Change: `progress/changes/20260908-M02-documents-preview-download-http.md` (approved).
- Mainline process: `progress/changes/20260908-M00-mainline-development.md`.
- Progress: `PROGRESS.md`, `progress/modules/M02.md`, `progress/modules/M11.md`.
- Repo handoff (product/process, not chat): `HANDOFF.md`.
- Impl: `api/src/pivot/documents/{http,ports,service,signatures}.py`; Fake `ObjectStore.get` in `tests/unit/documents/fakes.py`.
- Tests: `tests/unit/documents/test_FR_RBAC_003_preview.py`, `tests/integration/pipeline/test_FR_RBAC_003_http_preview.py`.

## Next session focus: composition root

Goal: make FastAPI startable without the test harness injecting every service. Today `create_app()` only mounts routes when services are passed in; there is no `main.py` / Dockerfile / Compose api service.

Constraints from repo `HANDOFF.md` §5:

1. Composition root first (uvicorn-capable app, Argon2, storage behind ports).
2. Then Next rewrite/proxy so `/api/v1` works from the web app.
3. Do not freeze `TBD-P0`. Do not mark GATE-P0 verified.
4. If the slice needs a public-contract or ownership change, write `progress/changes/` first (DoR).

Known related gaps (do not “fix green” by weakening auth): password hasher dual-path (Argon2 exists, HTTP tests use PBKDF2); login limiter is a no-op; PATCH admin user only handles `status`.

## Working tree note

Untracked `问枢Pivot-技术方案V2.md` at repo root. Historical spec; **do not add/commit**. Leave it for Owner.

## Suggested skills

Call these via the Skill tool at the start of the next session:

1. **tdd** — SPEC §0.4 Red → Contract → Green. New composition-root behavior needs `test_<requirement_id>_<behavior>()` before production wiring (likely `NFR-OBS-001/002` plus a boot/assembly test; do not invent GATE verified).
2. **codebase-design** — composition root is a seam: keep `create_app` a thin assembler; do not dump domain logic into `api/src/pivot/http/**` (MODULE_SPEC M11 rule).
3. **diagnosing-bugs** — only if boot, import, or hasher/storage wiring fails.

Do not use worktree/subagent isolation for this mainline slice unless Owner asks.
