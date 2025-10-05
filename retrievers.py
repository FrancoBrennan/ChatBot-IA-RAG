# retrievers.py
import os
# retrievers.py
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever

from langchain_openai import ChatOpenAI
from langchain.retrievers.multi_query import MultiQueryRetriever  

from vectorstore_langchain import load_faiss, build_faiss, build_bm25, INDEX_DIR
from rerank import CrossEncoderReranker  # si no querés rerank, comentá esta import

def ensure_faiss(dir_path: str | None = None) -> FAISS:
    dir_path = dir_path or INDEX_DIR
    try:
        return load_faiss(dir_path)
    except Exception:
        return build_faiss(dir_path)

def base_hybrid(dir_path: str | None = None) -> EnsembleRetriever:
    faiss_vs = ensure_faiss(dir_path)
    dense_ret = faiss_vs.as_retriever(search_type="similarity", search_kwargs={"k": 12})
    sparse_ret: BM25Retriever = build_bm25()
    return EnsembleRetriever(retrievers=[dense_ret, sparse_ret], weights=[0.85, 0.5])

def build_pro_retriever(model_name: str | None = None, faiss_dir: str | None = None):
    model_name = model_name or os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct")
    llm = ChatOpenAI(model=model_name, temperature=0)
    base = base_hybrid(faiss_dir)
    mqr = MultiQueryRetriever.from_llm(retriever=base, llm=llm)

    # activá/desactivá rerank por env (RERANK=0 para desactivar)
    use_rerank = os.getenv("RERANK", "1") != "0"
    reranker = CrossEncoderReranker(top_n=8) if use_rerank else None

    class FinalRetriever:
        # API nueva
        def invoke(self, q: str):
            docs = mqr.invoke(q)  # evita DeprecationWarning
            if reranker:
                return reranker.rerank(q, docs)
            return docs

        # Compat con código viejo
        def get_relevant_documents(self, q: str):
            # usamos la misma ruta para mantener un solo camino
            return self.invoke(q)

    return FinalRetriever()
