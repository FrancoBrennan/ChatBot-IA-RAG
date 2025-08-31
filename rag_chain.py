from typing import List, Tuple, Dict, Optional
import os, re
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from retrievers import build_pro_retriever
from utils import registrar_consulta_no_resuelta  # inserta en DB

INSUFF_MSG = "No tengo información suficiente en la base para responder eso."

SYSTEM_PROMPT = (
    "Sos un asistente técnico. Respondé SOLO con el contexto provisto. "
    f"Si el contexto no alcanza, devolvé exactamente: \"{INSUFF_MSG}\" "
    "Sé claro, directo y práctico. Cuando corresponda, usá listas/pasos y Markdown. "
    "No inventes datos fuera del contexto."
    "NO CITES TÍTULOS, NOMBRES DE ARCHIVOS Y DEMÁS EN TUS RESPUESTAS, SOS VOS QUIEN TIENE QUE DAR LA INFORMACIÓN, NO DECIRLE AL USUARIO QUE LO LEA ÉL."
)

def _ensure_openrouter_env():
    if not os.getenv("OPENAI_API_KEY") and os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    if not os.getenv("OPENAI_BASE_URL") and os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"

def _make_llm(model_name: Optional[str] = None) -> ChatOpenAI:
    _ensure_openrouter_env()
    model = model_name or os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct")
    return ChatOpenAI(model=model, temperature=0, max_tokens=800)

def _collect_sources(docs: List[Document]) -> List[Dict]:
    agg: Dict[str, Dict[str, Optional[int]]] = {}
    for d in docs:
        src = d.metadata.get("source", "desconocido")
        page = d.metadata.get("page", None)
        if src not in agg:
            agg[src] = {"min": None, "max": None}
        if isinstance(page, int):
            agg[src]["min"] = page if agg[src]["min"] is None else min(agg[src]["min"], page)
            agg[src]["max"] = page if agg[src]["max"] is None else max(agg[src]["max"], page)
    out: List[Dict] = []
    for src, span in agg.items():
        if span["min"] is not None:
            out.append({
                "archivo": src,
                "paginas": f"{span['min']}-{span['max']}" if span["min"] != span["max"] else f"{span['min']}"
            })
        else:
            out.append({"archivo": src})
    # dedupe
    seen, uniq = set(), []
    for s in out:
        key = (s["archivo"], s.get("paginas"))
        if key not in seen:
            seen.add(key); uniq.append(s)
    return uniq

def _format_docs(docs: List[Document]) -> str:
    return "\n\n".join(d.page_content for d in docs)

# ---------- Filtro OOD: intersección de tokens de contenido ----------
_WORD_RE = re.compile(r"[a-záéíóúüñ0-9]{3,}", re.IGNORECASE)
STOPWORDS = {
    # ES
    "que","de","la","el","los","las","y","o","u","a","en","con","por","para","un","una","uno","al","del",
    "se","es","son","ser","estoy","estas","esta","está","están","estamos","como","cuando","donde","cuanto",
    "cual","cuales","porqué","porque","pero","si","no","ya","mas","más","menos","muy","tambien","también",
    "sobre","entre","hoy","ayer","mañana","tengo","tienes","tiene","puedo","puedes","puede",
    # EN básicos
    "the","and","or","to","of","in","on","for","a","an","is","are","was","were","be","been","do","does","did","can","could"
}

def _token_set(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))

def _content_token_set(text: str) -> set[str]:
    return {t for t in _token_set(text) if t not in STOPWORDS}

def _content_intersection_size(question: str, docs: List[Document]) -> int:
    """Cantidad de palabras 'de contenido' compartidas entre la pregunta y docs top."""
    qset = _content_token_set(question)
    if not qset:
        return 0
    joined = " ".join(d.page_content for d in docs[:5])
    dset = _content_token_set(joined)
    return len(qset & dset)
# --------------------------------------------------------------------

def build_rag(model_name: Optional[str] = None):
    llm = _make_llm(model_name)
    retriever = build_pro_retriever(model_name=model_name or os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct"))

    def answer(question: str) -> Tuple[str, List[Dict]]:
        q = (question or "").strip()
        if len(q) < 3:
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        # API nueva (evita DeprecationWarning)
        docs = retriever.invoke(q)

        # Umbral de “suficiencia” más laxo
        total_len = sum(len(d.page_content) for d in docs)
        if (len(docs) < 1) or (total_len < 400):
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        # OOD: si no hay ninguna palabra de contenido en común => fuera de dominio
        inter = _content_intersection_size(q, docs)
        if inter == 0:
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        context = _format_docs(docs)
        msgs = [
            ("system", SYSTEM_PROMPT),
            ("user",
             f"Pregunta: {q}\n\n"
             f"Contexto (extractos relevantes):\n{context}\n\n"
             "Redactá una respuesta completa y bien estructurada en español. "
             "Si hay varios puntos/acciones, presentalos como lista numerada o viñetas. "
             "Incluí pasos concretos y advertencias cuando aplique.")
        ]
        out = (llm.invoke(msgs).content or "").strip()

        if not out or out == INSUFF_MSG:
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        return out, _collect_sources(docs)

    return answer
