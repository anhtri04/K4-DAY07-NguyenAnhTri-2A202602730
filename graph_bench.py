"""Graph-vs-vector limit comparison on the same 8 KTX benchmark queries.

Graph extractor: LLM (DeepSeek-compatible) if a key is configured,
otherwise the deterministic regex fallback. Vector side uses a
bag-of-words semantic embedder so the comparison tests retrieval
structure, not the mock embedder's randomness.

Usage:
    python graph_bench.py
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from dotenv import load_dotenv

from bench import QUERIES, load_documents, score_query
from src.graph_rag import GraphStore, LLMExtractor, RegexExtractor
from src.store import EmbeddingStore

load_dotenv()

CACHE_PATH = Path("data/graph_triples.json")


def build_graph(docs):
    try:
        extractor = LLMExtractor()
        name = f"llm({extractor.model})"
    except RuntimeError as error:
        print(f"LLM unavailable ({error}); using regex fallback.")
        extractor = RegexExtractor()
        name = "regex-fallback"
    graph = GraphStore()
    if name.startswith("llm") and CACHE_PATH.exists():
        saved = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if saved.get("model") == extractor.model and saved.get("triples"):
            print(f"Loaded {len(saved['triples'])} cached triples ({CACHE_PATH}).")
            for t in saved["triples"]:
                graph.add_triples([t], t.get("chunk", ""))
            return graph, name + "+cache"
    collected = []
    for doc in docs:
        triples = extractor.extract(doc.content, doc.metadata["doc_id"])
        for t in triples:
            t["chunk"] = doc.content
        collected.extend(triples)
        graph.add_triples(triples, doc.content)
    if name.startswith("llm"):
        CACHE_PATH.write_text(json.dumps({"model": extractor.model, "triples": collected}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Cached {len(collected)} triples to {CACHE_PATH}.")
    return graph, name


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

    return embed


def main() -> None:
    docs = load_documents()
    graph, extractor_name = build_graph(docs)
    print(f"Graph: extractor={extractor_name} entities={graph.entity_count()} triples={graph.triple_count()}")

    store = EmbeddingStore(collection_name="gv_compare")
    store._embedding_fn = bow_embedder([d.content for d in docs])
    store.add_documents(docs)

    totals = {"graph": 0, "vector": 0}
    for q in QUERIES:
        g_results = graph.retrieve(q["question"], top_k=3)
        v_results = store.search_with_filter(q["question"], top_k=3, metadata_filter=q["filter"])
        g_points, g_verdict = score_query(g_results, q["gold_doc"], q["gold_snippet"])
        v_points, v_verdict = score_query(v_results, q["gold_doc"], q["gold_snippet"])
        totals["graph"] += g_points
        totals["vector"] += v_points
        print(f"\n[{q['id']}] {q['question']}")
        print(f"  graph : {g_points}pts ({g_verdict})")
        for r in g_results:
            print(f"    score={r['score']:.3f} doc={r['metadata'].get('doc_id')} | {r['content'][:90]}")
        print(f"  vector: {v_points}pts ({v_verdict})")
        for r in v_results:
            print(f"    score={r['score']:.3f} doc={r['metadata'].get('doc_id')}")
    print(f"\nTOTAL graph={totals['graph']}/{2 * len(QUERIES)} vector={totals['vector']}/{2 * len(QUERIES)}")


if __name__ == "__main__":
    main()
