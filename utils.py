import fitz  # PyMuPDF
from sqlalchemy import text                # ✅ FALTABA ESTE IMPORT
from database import engine                # ✅ Usa el engine correcto


def extraer_texto_pdf(file_path: str) -> list[tuple[int, str]]:
    paginas = []
    with fitz.open(file_path) as doc:
        for i, page in enumerate(doc):
            texto = page.get_text().strip()
            if texto:
                paginas.append((i + 1, texto))  # Página 1-indexada
    return paginas


# --- Preguntas no resueltas ---------------------------------------------------

def _ensure_unresolved_table() -> None:
    """Crea la tabla si no existe (id, pregunta, fecha)."""
    with engine.begin() as conn:  # begin => abre transacción y commitea al salir
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS consultas_no_resueltas (
              id INT AUTO_INCREMENT PRIMARY KEY,
              pregunta TEXT NOT NULL,
              fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

def registrar_consulta_no_resuelta(pregunta: str) -> None:
    """Inserta la pregunta en consultas_no_resueltas (ignora strings vacíos)."""
    try:
        p = (pregunta or "").strip()
        if not p:
            return
        _ensure_unresolved_table()
        with engine.begin() as conn:  # ✅ transacción con autocommit
            conn.execute(
                text("INSERT INTO consultas_no_resueltas (pregunta) VALUES (:p)"),
                {"p": p}
            )
    except Exception as e:
        # Dejá este print para ver cualquier problema en consola
        print(f"[ERROR] registrar_consulta_no_resuelta: {type(e).__name__}: {e}")
