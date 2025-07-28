import fitz  # PyMuPDF

def extraer_texto_pdf(file_path: str) -> list[tuple[int, str]]:
    paginas = []
    with fitz.open(file_path) as doc:
        for i, page in enumerate(doc):
            texto = page.get_text().strip()
            if texto:
                paginas.append((i + 1, texto))  # Página 1-indexada
    return paginas
