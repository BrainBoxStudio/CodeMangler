# CodeMangler

A local-first CLI that scans a file, folder, or pasted text for sensitive information
(secrets, credentials, PII, internal hostnames, etc.), replaces it with realistic fake
values, and produces a reversible JSON mapping so the original values can be restored
later. No source code or detected secrets are ever sent to a cloud service — all
detection runs locally, and optional LLM assistance only talks to a local Ollama or
llama.cpp endpoint that you explicitly enable.

See [claude.md](claude.md) for the full functional specification.

## Status

Phase 1 (MVP): CLI, input handling, language detection, secret/PII detection, fake-value
replacement, mapping JSON, restore mode. Identifier renaming (Phase 2) and local LLM
providers (Phase 3) are not implemented yet.

## Install

```bash
pip install -e ".[dev]"
```

Optional extras:

```bash
pip install -e ".[pii]"   # Presidio + spaCy NLP-based PII detection
pip install -e ".[llm]"   # HTTP client for local Ollama / llama.cpp providers
pip install -e ".[code]"  # tree-sitter based identifier renaming (Phase 2)
```

If you install `[pii]`, download a spaCy model once (requires internet the first time):

```bash
python -m spacy download en_core_web_sm
```

Without it, `pii_detector` is skipped automatically and regex/detect-secrets detection
still covers emails, phone numbers, IPs, hostnames, and URLs.

## CLI usage

```bash
codemangler scan --input ./src
codemangler sanitize --input ./src --output ./sanitized --map sanitization_map.json
codemangler sanitize --text "password=abc123"
codemangler restore --input ./sanitized --output ./restored --map sanitization_map.json
```

Add `--encrypt-map --password <pw>` to `sanitize` to encrypt the mapping file (it
contains your original sensitive values in plain text otherwise — never share it
publicly). Pass `--password <pw>` to `restore` to decrypt it.

## Tests

```bash
pytest
```
