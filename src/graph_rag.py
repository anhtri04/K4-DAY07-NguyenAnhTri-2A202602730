"""Lab-scale Graph RAG sidecar: LLM triple extraction + adjacency-list graph.

Uses an OpenAI-compatible chat API (default: DeepSeek) for NER/triple
extraction. No API key needed for the regex fallback or for graph
traversal itself. Never commit API keys: configuration is env-only.

Env:
    GRAPH_NER_BASE_URL  default https://api.deepseek.com
    GRAPH_NER_API_KEY   fallback DEEPSEEK_API_KEY, then OPENAI_API_KEY
    GRAPH_NER_MODEL     default deepseek-chat
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict, deque
from typing import Any


def _ner_config() -> tuple[str, str, str]:
    base_url = os.getenv("GRAPH_NER_BASE_URL", "https://api.deepseek.com").strip()
    api_key = os.getenv("GRAPH_NER_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    model = os.getenv("GRAPH_NER_MODEL", "deepseek-flash").strip()
    return base_url, api_key, model


EXTRACTION_PROMPT = """Trich xuat cac su kien dang bo ba (head, relation, tail) tu van ban quy dinh ky tuc xa.
Van ban khong dau. Chi dung thong tin co trong van ban. Tra ve JSON array, moi phan tu co 3 khoa "head", "relation", "tail".
Vi du: [{"head": "Phong 4 sinh vien", "relation": "co phi", "tail": "450000 dong mot thang"}]

Van ban:
\"\"\"{text}\"\"\"
"""


class LLMExtractor:
    """Triple extractor backed by any OpenAI-compatible chat API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        default_base, default_key, default_model = _ner_config()
        self.base_url = base_url or default_base
        self.api_key = api_key or default_key
        self.model = model or default_model
        if not self.api_key:
            raise RuntimeError("Missing API key: set GRAPH_NER_API_KEY (or DEEPSEEK_API_KEY).")

    def extract(self, text: str, source_doc: str = "") -> list[dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": EXTRACTION_PROMPT.replace("{text}", text[:4000])}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        payload = response.choices[0].message.content or "{}"
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", payload, re.S)
            data = json.loads(match.group(0)) if match else []
        triples = data.get("triples", data) if isinstance(data, dict) else data
        return [
            {"head": t["head"], "relation": t["relation"], "tail": t["tail"], "source_doc": source_doc}
            for t in triples
            if isinstance(t, dict) and all(k in t for k in ("head", "relation", "tail"))
        ]


class RegexExtractor:
    """Deterministic fallback: targeted patterns for the KTX corpus style."""

    PATTERNS = [
        (re.compile(r"[Pp]hong (\d+) sinh vien:\s*([^\n.]+)", re.S), lambda m: (f"Phong {m.group(1)} sinh vien", "co phi", m.group(2).strip())),
        (re.compile(r"[Cc]ong[^\n.]*dong luc\s+([^\n.]+)", re.S), lambda m: ("Cong ky tuc xa", "dong luc", m.group(1).strip())),
        (re.compile(r"[Dd]at coc\s+([^\n.]+)", re.S), lambda m: ("Tien dat coc", "muc", m.group(1).strip())),
        (re.compile(r"[Tt]rong vong\s+([^\n.]+)", re.S), lambda m: ("Ket qua thu tuc", "thoi han", m.group(1).strip())),
        (re.compile(r"[Vv]i pham lan (hai|ba)[^\n.]*bi\s+([^\n.]+)", re.S), lambda m: (f"Vi pham lan {m.group(1)}", "bi xu ly", m.group(2).strip())),
    ]

    def extract(self, text: str, source_doc: str = "") -> list[dict[str, Any]]:
        triples = []
        for pattern, build in self.PATTERNS:
            for match in pattern.finditer(text):
                head, relation, tail = build(match)
                triples.append({"head": head, "relation": relation, "tail": tail, "source_doc": source_doc})
        return triples


class GraphStore:
    """In-memory knowledge graph: adjacency list, 2-hop traversal retrieval."""

    def __init__(self) -> None:
        self._forward: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._chunk_text: dict[tuple[str, str, str], str] = {}

    def add_triples(self, triples: list[dict[str, Any]], chunk_text: str = "") -> None:
        for triple in triples:
            head = triple["head"].strip()
            record = {"relation": triple["relation"], "tail": triple["tail"], "source_doc": triple.get("source_doc", "")}
            self._forward[head].append(record)
            self._chunk_text[(head, triple["relation"], triple["tail"])] = chunk_text

    def entity_count(self) -> int:
        return len(self._forward)

    def triple_count(self) -> int:
        return sum(len(edges) for edges in self._forward.values())

    def _link_entities(self, query: str) -> list[str]:
        lowered = query.lower()
        return [head for head in self._forward if head.lower() in lowered]

    def retrieve(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        seeds = self._link_entities(query)
        if not seeds:
            # Fallback: any node sharing a content word with the query.
            query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
            seeds = [h for h in self._forward if query_words & set(re.findall(r"[a-z0-9]+", h.lower()))]
        # Most specific seed first: longer label + lower fan-out wins.
        # Hub nodes like "Sinh vien" match everything and drown the ranking.
        seeds = sorted(seeds, key=lambda h: (-len(h), len(self._forward.get(h, []))))
        visited: dict[tuple[str, str, str], tuple[int, int]] = {}
        queue: deque[tuple[str, int, int]] = deque((seed, 0, rank) for rank, seed in enumerate(seeds))
        seen_nodes = set(seeds)
        while queue:
            node, hops, seed_rank = queue.popleft()
            if hops >= 2:
                continue
            for edge in self._forward.get(node, []):
                key = (node, edge["relation"], edge["tail"])
                if key not in visited:
                    visited[key] = (hops + 1, seed_rank)
                if edge["tail"] not in seen_nodes:
                    seen_nodes.add(edge["tail"])
                    queue.append((edge["tail"], hops + 1, seed_rank))
        ranked = sorted(visited.items(), key=lambda item: (item[1][0], item[1][1]))
        results = []
        for (head, relation, tail), (hops, _) in ranked[: max(0, top_k)]:
            chunk = self._chunk_text.get((head, relation, tail), "")
            results.append(
                {
                    "content": f"{head} --{relation}--> {tail} | {chunk[:200]}".strip(),
                    "score": round(1.0 / (1 + hops), 3),
                    "metadata": {"doc_id": next(
                        (e["source_doc"] for e in self._forward.get(head, []) if e["tail"] == tail), ""
                    )},
                }
            )
        return results
