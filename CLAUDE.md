# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**IMPORTANT:** Follow documentation rules in [CONTRIBUTING.md](CONTRIBUTING.md) - especially the file creation and naming conventions.

## Project Overview

`notebooklm-py` is an unofficial Python client for Google NotebookLM that uses undocumented RPC APIs. The library enables programmatic automation of NotebookLM features including notebook management, source integration, AI querying, and studio artifact generation (podcasts, videos, quizzes, etc.).

**Critical constraint**: This uses Google's internal `batchexecute` RPC protocol with obfuscated method IDs that Google can change at any time. All RPC method IDs in `src/notebooklm/rpc/types.py` are undocumented and subject to breakage.

## Development Commands

```bash
# Create/recreate venv with uv (recommended - relocatable venvs)
uv venv .venv
uv pip install -e ".[all]"
playwright install chromium

# Activate virtual environment
source .venv/bin/activate

# Run all tests (excluding e2e by default)
pytest

# Run a single test file
pytest tests/unit/test_decoder.py

# Run a single test by name
pytest tests/unit/test_decoder.py::TestClass::test_method

# Run with coverage
pytest --cov

# Run e2e tests (requires authentication)
pytest tests/e2e -m e2e

# CLI testing
notebooklm --help
```

## Pre-Commit Checks (REQUIRED before committing)

**IMPORTANT:** Always run these checks before committing to avoid CI failures:

```bash
ruff format src/ tests/ && ruff check src/ tests/ && mypy src/notebooklm --ignore-missing-imports && pytest
```

## Architecture

### Layered Design

```text
CLI Layer (cli/)
    ↓
Client Layer (client.py, _*.py APIs)
    ↓
Core Layer (_core.py)
    ↓
RPC Layer (rpc/)
```

1. **RPC Layer** (`src/notebooklm/rpc/`):
   - `types.py`: All RPC method IDs and enums (source of truth)
   - `encoder.py`: Request encoding
   - `decoder.py`: Response parsing

2. **Core Layer** (`src/notebooklm/_core.py`):
   - HTTP client management
   - RPC call abstraction
   - Request counter handling

3. **Client Layer** (`src/notebooklm/client.py`, `_*.py`):
   - `NotebookLMClient`: Main async client with namespaced APIs
   - `_notebooks.py`, `_sources.py`, `_artifacts.py`, etc.: Domain APIs

4. **CLI Layer** (`src/notebooklm/cli/`):
   - Modular Click commands
   - `session.py`, `notebook.py`, `source.py`, `generate.py`, etc.

### Key Files

| File | Purpose |
| --- | --- |
| `client.py` | Main `NotebookLMClient` class |
| `_core.py` | HTTP and RPC infrastructure |
| `_notebooks.py` | `client.notebooks` API |
| `_sources.py` | `client.sources` API |
| `_artifacts.py` | `client.artifacts` API |
| `_chat.py` | `client.chat` API |
| `_settings.py` | `client.settings` API (output language, etc.) |
| `_sharing.py` | `client.sharing` API |
| `_research.py` | `client.research` API |
| `_notes.py` | `client.notes` API |
| `rpc/types.py` | RPC method IDs (source of truth) |
| `auth.py` | Authentication handling |
| `cli/` | CLI command modules |

### Repository Structure

```text
src/notebooklm/
├── __init__.py          # Public exports
├── client.py            # NotebookLMClient
├── auth.py              # Authentication
├── types.py             # Dataclasses
├── exceptions.py        # Exception types
├── paths.py             # Storage paths
├── _core.py             # Core infrastructure
├── _notebooks.py        # NotebooksAPI
├── _sources.py          # SourcesAPI
├── _artifacts.py        # ArtifactsAPI
├── _chat.py             # ChatAPI
├── _research.py         # ResearchAPI
├── _notes.py            # NotesAPI
├── _settings.py         # SettingsAPI
├── _sharing.py          # SharingAPI
├── _url_utils.py        # URL helpers
├── _logging.py          # Logging setup
├── _version_check.py    # Python version guard
├── rpc/                 # RPC protocol layer
│   ├── types.py         # Method IDs and enums
│   ├── encoder.py       # Request encoding
│   └── decoder.py       # Response parsing
└── cli/                 # CLI implementation
    ├── helpers.py        # Shared utilities
    ├── options.py        # Shared Click options
    ├── grouped.py        # Command group wrappers
    ├── error_handler.py  # CLI error handling
    ├── session.py        # login, use, status, clear
    ├── notebook.py       # list, create, delete, rename
    ├── source.py         # source add, list, delete
    ├── artifact.py       # artifact commands
    ├── generate.py       # generate audio, video, etc.
    ├── download.py       # download commands
    ├── download_helpers.py # download utilities
    ├── chat.py           # ask, configure, history
    ├── note.py           # note commands
    ├── research.py       # research commands
    ├── share.py          # share commands
    ├── skill.py          # skill commands
    └── language.py       # language commands
```

## API Patterns

### Client Usage

```python
# Correct pattern - uses namespaced APIs
async with await NotebookLMClient.from_storage() as client:
    notebooks = await client.notebooks.list()
    await client.sources.add_url(nb_id, url)
    result = await client.chat.ask(nb_id, question)
    status = await client.artifacts.generate_audio(nb_id)
```

### CLI Structure

Commands are organized as:

- **Top-level**: `login`, `use`, `status`, `clear`, `list`, `create`, `ask`
- **Grouped**: `source add`, `artifact list`, `generate audio`, `download video`, `note create`

## Testing Strategy

- **Unit tests** (`tests/unit/`): Test encoding/decoding, no network
- **Integration tests** (`tests/integration/`): Mock HTTP responses via VCR cassettes (`tests/cassettes/`)
- **E2E tests** (`tests/e2e/`): Real API, require auth, marked `@pytest.mark.e2e`

### E2E Test Status

- ✅ Notebook operations (list, create, rename, delete)
- ✅ Source operations (add URL/text/YouTube, rename)
- ✅ Download operations (audio, video, infographic, slides)
- ⚠️ Artifact generation may fail due to rate limiting

## Common Pitfalls

1. **RPC method IDs change**: Check network traffic and update `rpc/types.py`
2. **Nested list structures**: Params are position-sensitive. Check existing implementations.
3. **Source ID nesting**: Different methods need `[id]`, `[[id]]`, `[[[id]]]`, or `[[[[id]]]]`
4. **CSRF tokens expire**: Use `client.refresh_auth()` or re-run `notebooklm login`
5. **Rate limiting**: Add delays between bulk operations

## Documentation

All docs use lowercase-kebab naming in `docs/`:

- `docs/cli-reference.md` - CLI commands
- `docs/python-api.md` - Python API reference
- `docs/configuration.md` - Storage and settings
- `docs/troubleshooting.md` - Known issues
- `docs/development.md` - Architecture, testing, releasing
- `docs/rpc-development.md` - RPC capture and debugging
- `docs/rpc-reference.md` - RPC payload structures

## AI Agent Rules (from CONTRIBUTING.md)

### File Creation

1. **No Root Rule** - Never create `.md` files in the repository root unless explicitly instructed.
2. **Modify, Don't Fork** - Edit existing files; never create `FILE_v2.md` or `FILE_updated.md` duplicates.
3. **Scratchpad Protocol** - All analysis and intermediate work goes in `docs/scratch/` with date prefix: `YYYY-MM-DD-<context>.md`
4. **Consolidation First** - Before creating new docs, search for existing related docs and update them instead.

### Protected Sections

Never modify content between `PROTECTED` and `END PROTECTED` markers unless explicitly instructed by the user.

### Naming Conventions

| Type | Format | Example |
| --- | --- | --- |
| Root GitHub files | `UPPERCASE.md` | `README.md`, `CONTRIBUTING.md` |
| Agent files | `UPPERCASE.md` | `CLAUDE.md`, `AGENTS.md` |
| All other docs/ files | `lowercase-kebab.md` | `cli-reference.md` |
| Scratch files | `YYYY-MM-DD-context.md` | `2026-01-06-debug-auth.md` |

## When to Suggest CLI vs API

- **CLI**: Quick tasks, shell scripts, LLM agent automation
- **Python API**: Application integration, complex workflows, async operations

## Pull Request Workflow (REQUIRED)

After creating a PR, you MUST monitor and address feedback:

### 1. Monitor CI Status

```bash
gh pr checks <PR_NUMBER>
```

### 2. Check for Review Comments

```bash
gh api repos/teng-lin/notebooklm-py/pulls/<PR_NUMBER>/comments \
  --jq '.[] | "File: \(.path):\(.line)\nComment: \(.body)\n---"'
```

### 3. Address Feedback

For each review comment (especially from `gemini-code-assist`):

1. Read and understand the feedback
2. Make the suggested fix if it improves the code
3. Commit with a descriptive message referencing the feedback
4. Push and re-check CI
5. **Reply to the review thread** confirming the fix:

   ```bash
   gh api repos/teng-lin/notebooklm-py/pulls/<PR>/comments/<COMMENT_ID>/replies \
     -f body="Addressed in commit <SHA>: <brief description>"
   ```

### 4. Verify Final State

```bash
gh pr view <PR_NUMBER> --json state,mergeStateStatus,mergeable
```

**Important**: Do NOT consider a PR complete until:

- All CI checks pass
- All review comments are addressed
- `mergeStateStatus` is `CLEAN`
