# AGENTS.md — Day 7 Data Foundations Lab (K4-L3A)

## Setup
- Python 3.11 per `.python-version`. Core deps only: `pip install -r requirements.txt` (`pytest`, `python-dotenv`). All graded tests run on the mock embedder — no real backend needed.
- Optional backends (benchmark quality only, not graded): `requirements-local.txt` (sentence-transformers), `pip install openai`, `pip install google-genai`. First local run downloads PyTorch + model.
- `.env` is gitignored — never commit keys. Copy `.env.example` to `.env`.

## Verify
- `pytest tests/ -v` — single source of truth (~40 tests). Tests import via `LAB_SOLUTION_PACKAGE` env (default `src`); keep public names in `src/__init__.py` stable.
- Manual demo: `python3 main.py ["question"]`. Only `.md`/`.txt` in `SAMPLE_FILES` are loaded; missing files are skipped, not errors.
- Benchmarks: `python bench.py | tee ket_qua_benchmark.txt`, `python graph_bench.py`, `python compare.py [--mock | --embed openai] [--audience student] ["query"]` (no args = interactive prompt, `rich` required).

## Architecture
- `src/models.py`: `Document(id, content, metadata)` dataclass.
- `src/chunking.py`: `FixedSizeChunker` (sliding window, `step = chunk_size - overlap`), `SentenceChunker` (regex `(?<=[.!?])\s+`, groups N sentences), `RecursiveChunker` (separators `["\n\n","\n",". "," ",""]`, recurse then merge to `chunk_size`), `compute_similarity` (cosine, returns `0.0` on zero-norm), `ChunkingStrategyComparator.compare()` (fixed/overlap=0 vs sentences/3 vs recursive).
- `src/embeddings.py`: `MockEmbedder` (deterministic MD5-seeded, dim 64, L2-normalized), `LocalEmbedder` (paraphrase-multilingual-MiniLM-L12-v2), `OpenAIEmbedder` (`text-embedding-3-small`, honors `OPENAI_BASE_URL`), `GeminiEmbedder` (`gemini-embedding-001`, needs `GEMINI_API_KEY` or `GOOGLE_API_KEY`), `_mock_embed` singleton.
- `src/store.py`: `EmbeddingStore` is **in-memory only** (Chroma branch disabled, no `chromadb` dep). `add_documents` auto-sets `metadata["doc_id"]`; `search` ranks by dot product; `search_with_filter` does exact-match metadata prefilter (`None`/`{}` = no filter); `delete_document` matches on `metadata.doc_id`.
- `src/agent.py`: `KnowledgeBaseAgent.answer()` — retrieve top-k → build `ONLY context` prompt with `[1]/[2]/[3]` cites → call `llm_fn`. Empty store/no results returns `"No relevant documents found in the knowledge base."`.
- `src/graph_rag.py` (sidecar): `RegexExtractor` (deterministic KTX patterns) vs `LLMExtractor` (DeepSeek-compatible chat API), `GraphStore` (adjacency list, 2-hop traversal, longest-label seed first). Caches triples in `data/graph_triples.json`.
- `main.py` imports public API from `src`; `bench.py` chunk-then-ingest pattern: each chunk becomes a `Document(id="{stem}#{i}", metadata={**frontmatter, "doc_id": stem})`.

## Env / provider rules
- `main.py`, `compare.py`, `graph_bench.py` call `load_dotenv()`; library code in `src/` does not. Standalone snippets need `export VAR=...` or explicit `load_dotenv()`.
- `EMBEDDING_PROVIDER=mock|local|openai|gemini` (default `mock`). Unknown/misconfigured provider silently falls back to `_mock_embed`.
- Graph RAG env: `GRAPH_NER_BASE_URL` (default `https://api.deepseek.com`), key priority `GRAPH_NER_API_KEY > DEEPSEEK_API_KEY > OPENAI_API_KEY`, `GRAPH_NER_MODEL` (default `deepseek-flash`).

## K4-L3A corpus constraints
- Phase 2 corpus is university dorm/services (`data/ky-tuc-xa/`, `data/university/`), 5–10 docs. Each doc metadata must include `audience` (`student|faculty|staff|all`) + `source_url`, `retrieved_at`, `document_version`.
- Q1 in `bench.py` requires `metadata_filter={"audience": "student"}` (staff doc claims 24/24 gate); keep the mandatory with/without-filter A/B. Content-level scoring checks `gold_snippet` in chunk text, not just doc hit.
- `bench.py`: each member copies the file and changes **only** `make_chunker()`.
- `scripts/fetch_public_pages.py`: conservative fetcher — enforces robots.txt, `--delay >= 1s`, accepts only HTML/text, input CSV must have `url` column, writes `.md` + `sources.csv` manifest. No personal/credential/internal content in `data/`.

## Conventions
- No CI, linter, formatter, or typechecker — `pytest` is the only gate.
- Don't add `chromadb` or assume persistence; `CHROMA_PERSIST_DIR` in `.env.example` is aspirational.
- `docs/INSTRUCTOR_GUIDE.md` is gitignored/instructor-only; don't reference it in student-facing output.
