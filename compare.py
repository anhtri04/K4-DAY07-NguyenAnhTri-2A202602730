"""Side-by-side Vector vs Graph RAG comparison CLI (Rich layout).

Query on top, Vector (left) vs Graph (right) below.

Usage:
    python compare.py "Dich vu giat ui o khu B mo cua den may gio?"
    python compare.py --audience student "Cong ky tuc xa dong luc may gio?"
    python compare.py --mock "Phong 4 sinh vien gia bao nhieu?"   # lab-default mock embedder
    python compare.py --embed openai "What is the checkout time?"  # real embedder via OPENAI_BASE_URL
    python compare.py                                              # interactive prompt
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from bench import load_documents
from src.graph_rag import GraphStore, LLMExtractor, RegexExtractor
from src.store import EmbeddingStore

load_dotenv()

CACHE_PATH = Path("data/graph_triples.json")
console = Console()


def bow_embedder(texts):
    vocab = sorted({w for t in texts for w in re.findall(r"[a-z0-9]+", t.lower())})
    index = {w: i for i, w in enumerate(vocab)}

    def embed(text):
        vector = [0.0] * len(vocab)
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            if word in index:
                vector[index[word]] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    embed._backend_name = "bow-semantic"
    return embed


def build_vector(docs, use_mock: bool, embed_name: str | None) -> tuple[EmbeddingStore, str]:
    from src.embeddings import _mock_embed

    store = EmbeddingStore(collection_name="compare_vector")
    if use_mock or (embed_name or "") == "mock":
        store._embedding_fn = _mock_embed
        name = "mock (lab default, no semantics)"
    elif (embed_name or "") in ("openai", "lmstudio", "local-server"):
        from src.embeddings import OpenAIEmbedder

        embedder = OpenAIEmbedder()
        try:
            embedder("connection probe")
        except Exception as error:
            console.print(
                "[red]Cannot reach the embeddings endpoint.[/red]\n"
                "Check: (1) LM Studio server is Started, (2) an embedding model is loaded,\n"
                f"(3) OPENAI_BASE_URL matches (current: {embedder.client.base_url}).\n"
                f"Detail: {error}"
            )
            raise SystemExit(1)
        store._embedding_fn = embedder
        name = f"openai-compatible ({store._embedding_fn._backend_name})"
    else:
        store._embedding_fn = bow_embedder([d.content for d in docs])
        name = "bow-semantic"
    store.add_documents(docs)
    return store, name


def build_graph(docs) -> tuple[GraphStore, str]:
    graph = GraphStore()
    if CACHE_PATH.exists():
        saved = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        for t in saved.get("triples", []):
            graph.add_triples([t], t.get("chunk", ""))
        return graph, f"cached triples ({graph.triple_count()})"
    try:
        extractor: LLMExtractor | RegexExtractor = LLMExtractor()
        name = f"llm({extractor.model})"
    except RuntimeError:
        extractor = RegexExtractor()
        name = "regex-fallback"
    for doc in docs:
        graph.add_triples(extractor.extract(doc.content, doc.metadata["doc_id"]), doc.content)
    return graph, name


def result_table(title: str, results: list[dict], style: str) -> Panel:
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("#", width=3)
    table.add_column("score", width=7)
    table.add_column("doc", width=26)
    table.add_column("snippet", ratio=1)
    if not results:
        table.add_row("-", "-", "-", "no results")
    for rank, r in enumerate(results, start=1):
        snippet = r["content"][:160].replace("\n", " ")
        table.add_row(str(rank), f"{r['score']:.3f}", str(r["metadata"].get("doc_id", "")), snippet)
    return Panel(table, title=title, border_style=style)


def main() -> None:
    argv = sys.argv[1:]
    args: list[str] = []
    use_mock = "--mock" in argv
    audience = None
    embed_name = None
    skip_next = False
    for i, a in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if a == "--audience" and i + 1 < len(argv):
            audience = argv[i + 1]
            skip_next = True
        elif a == "--embed" and i + 1 < len(argv):
            embed_name = argv[i + 1]
            skip_next = True
        elif a.startswith("--"):
            continue
        else:
            args.append(a)
    if embed_name is None:
        import os as _os

        embed_name = _os.getenv("EMBEDDING_PROVIDER", "bow")
    query = " ".join(args).strip() or Prompt.ask("[bold]Nhap query[/bold]")
    metadata_filter = {"audience": audience} if audience else None

    with console.status("Loading corpus + stores..."):
        docs = load_documents()
        vector_store, vector_name = build_vector(docs, use_mock, embed_name)
        graph_store, graph_name = build_graph(docs)

    vector_results = vector_store.search_with_filter(query, top_k=3, metadata_filter=metadata_filter)
    graph_results = graph_store.retrieve(query, top_k=3)

    console.print(Panel(
        f"[bold]{query}[/bold]\nfilter={metadata_filter} | chunks={len(docs)}",
        title="Query / Test case", border_style="yellow",
    ))
    console.print(Columns([
        result_table(f"Vector RAG ({vector_name})", vector_results, "cyan"),
        result_table(f"Graph RAG ({graph_name})", graph_results, "magenta"),
    ]))


if __name__ == "__main__":
    main()
