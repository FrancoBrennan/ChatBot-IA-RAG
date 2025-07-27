import fitz  # PyMuPDF

def extraer_texto_pdf(file_path: str) -> str:
    texto = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            texto += page.get_text()
    return texto
