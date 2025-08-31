from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def split_text(text: str, meta: dict) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900, chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    return [Document(page_content=c, metadata=meta) for c in splitter.split_text(text)]
