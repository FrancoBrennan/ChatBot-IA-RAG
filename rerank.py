from typing import List
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2", top_n: int = 8):
        self.model = CrossEncoder(model_name)
        self.top_n = top_n

    def rerank(self, query: str, docs: List[Document]) -> List[Document]:
        if not docs:
            return docs
        pairs = [(query, d.page_content) for d in docs]
        scores = self.model.predict(pairs).tolist()
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[: self.top_n]]
