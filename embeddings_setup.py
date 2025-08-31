import os
from dotenv import load_dotenv
load_dotenv()

HF_MODEL = os.getenv("HF_EMBEDDING_MODEL", "intfloat/multilingual-e5-base")

try:
    from langchain_huggingface import HuggingFaceEmbeddings as HFEmbeddings
except Exception:
    from langchain_community.embeddings import HuggingFaceEmbeddings as HFEmbeddings

dense = HFEmbeddings(
    model_name=HF_MODEL,
    encode_kwargs={"normalize_embeddings": True},  # coseno via dot-product
    model_kwargs={"device": "cpu"}                 # usa "cuda" si tenés GPU
)
