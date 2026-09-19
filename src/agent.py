from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        if self.store.get_collection_size() == 0:
            return "No relevant documents found in the knowledge base."
        results = self.store.search(question, top_k=top_k)
        if not results:
            return "No relevant documents found in the knowledge base."
        context_lines = []
        for index, result in enumerate(results, start=1):
            source = result.get("metadata", {}).get("doc_id", result.get("id", "unknown"))
            context_lines.append(f"[{index}] (source: {source}) {result.get('content', '')}")
        context = "\n".join(context_lines)
        prompt = (
            "Answer the question using ONLY the context below. "
            "Cite the supporting chunk as [1], [2] or [3]. "
            "If the context does not contain the answer, say so explicitly.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        return self.llm_fn(prompt)
