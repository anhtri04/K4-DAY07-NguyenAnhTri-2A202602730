"""Personal benchmark runner — KTX corpus, RecursiveChunker strategy.

Each team member copies this file and changes ONLY `make_chunker()`.
Usage:
    python bench.py | tee ket_qua_benchmark.txt
"""

from __future__ import annotations

import re
from pathlib import Path

from src.chunking import RecursiveChunker
from src.models import Document
from src.store import EmbeddingStore

CORPUS_DIR = Path("data/ky-tuc-xa")


# === Strategy under test: change ONLY this function per member ===
def make_chunker():
    return RecursiveChunker(chunk_size=500)


QUERIES = [
    {
        "id": "Q1",
        "question": "Cong ky tuc xa dong luc may gio?",
        "gold_doc": "ktx-noi-quy-sinh-vien",
        "gold_snippet": "22 gio 30",
        "filter": {"audience": "student"},
        "note": "Can filter: staff doc noi cong mo 24/24 (xe cong vu).",
    },
    {
        "id": "Q2",
        "question": "Phong 4 sinh vien co muc phi bao nhieu mot thang?",
        "gold_doc": "ktx-muc-phi-sinh-vien",
        "gold_snippet": "450000",
        "filter": None,
        "note": "Tra so lieu cu the.",
    },
    {
        "id": "Q3",
        "question": "Ho so nhan phong ky tuc xa gom nhung giay to gi?",
        "gold_doc": "ktx-thu-tuc-giay-to",
        "gold_snippet": "can cuoc cong dan",
        "filter": None,
        "note": "Liet ke dieu kien/thu tuc.",
    },
    {
        "id": "Q4",
        "question": "Quy trinh dang ky phong o gom may buoc va khi nao co ket qua xet duyet?",
        "gold_doc": "ktx-dang-ky-phong-sinh-vien",
        "gold_snippet": "7 ngay lam viec",
        "filter": None,
        "note": "Hoi quy trinh nhieu buoc.",
    },
    {
        "id": "Q5",
        "question": "Sinh vien vi pham noi quy lan thu ba bi xu ly nhu the nao?",
        "gold_doc": "ktx-noi-quy-sinh-vien",
        "gold_snippet": "cham dut hop dong",
        "filter": None,
        "note": "Hoi che tai/muc xu ly.",
    },
]


def parse_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    front, body = raw.split("---", 2)[1:3]
    metadata = {}
    for key, value in re.findall(r"^(\w+):\s*(.+)$", front, re.M):
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, body.strip()


def load_documents() -> list[Document]:
    chunker = make_chunker()
    docs: list[Document] = []
    for path in sorted(CORPUS_DIR.glob("*.md")):
        frontmatter, body = parse_markdown(path)
        for i, chunk in enumerate(chunker.chunk(body)):
            docs.append(
                Document(
                    id=f"{path.stem}#{i}",
                    content=chunk,
                    metadata={**frontmatter, "doc_id": path.stem},
                )
            )
    return docs


def score_query(results: list[dict], gold_doc: str, gold_snippet: str) -> tuple[int, str]:
    """Content-level scoring: 2 = snippet in rank-1 chunk of gold doc,
    1 = snippet in rank-2/3, 0 = absent. Also reports doc-level hit."""
    doc_hit_rank = None
    for rank, r in enumerate(results, start=1):
        if r["metadata"].get("doc_id") == gold_doc and doc_hit_rank is None:
            doc_hit_rank = rank
        if r["metadata"].get("doc_id") == gold_doc and gold_snippet.lower() in r["content"].lower():
            return (2 if rank == 1 else 1), f"content-hit@{rank}"
    if doc_hit_rank is not None:
        return 0, f"doc-hit-only@{doc_hit_rank} (snippet missing -> inflated if scored by doc)"
    return 0, "miss"


def main() -> None:
    docs = load_documents()
    store = EmbeddingStore(collection_name="ktx_bench")
    store.add_documents(docs)
    print(f"Strategy: {make_chunker().__class__.__name__} | chunks: {len(docs)} | store: {store.get_collection_size()}")

    total = 0
    for q in QUERIES:
        results = store.search_with_filter(q["question"], top_k=3, metadata_filter=q["filter"])
        points, verdict = score_query(results, q["gold_doc"], q["gold_snippet"])
        total += points
        print(f"\n[{q['id']}] {q['question']}  filter={q['filter']}  gold={q['gold_doc']} -> {points}pts ({verdict})")
        for rank, r in enumerate(results, start=1):
            print(f"  {rank}. score={r['score']:.3f} doc={r['metadata'].get('doc_id')}")
            print(f"     {r['content'][:110].replace(chr(10), ' ')}...")
    print(f"\nTOTAL: {total}/10")

    # Mandatory A/B for the filter-dependent query.
    q1 = QUERIES[0]
    print(f"\n--- A/B {q1['id']} without filter ---")
    for rank, r in enumerate(store.search_with_filter(q1["question"], top_k=3, metadata_filter=None), start=1):
        print(f"  {rank}. score={r['score']:.3f} doc={r['metadata'].get('doc_id')}")


if __name__ == "__main__":
    main()
