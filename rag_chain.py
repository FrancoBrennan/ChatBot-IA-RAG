# rag_chain.py
from typing import List, Tuple, Dict, Optional
import os, re, unicodedata, json
import numpy as np
from rapidfuzz import process, fuzz
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from retrievers import build_pro_retriever
from embeddings_setup import dense
from utils import registrar_consulta_no_resuelta

# ------------------------ Mensajes base ------------------------
INSUFF_MSG = "No tengo información suficiente para responder a eso. Tu consulta será guardada y enviada al Help Desk. Gracias!"
NO_INDEX_MSG = "No hay documentos indexados."

SYSTEM_PROMPT = (
    "Eres un asistente que responde EXCLUSIVAMENTE en español. "
    "Usa SOLO la información de referencia provista. "
    "Si no hay información suficiente, responde ÚNICAMENTE con el mensaje estándar y nada más: "
    f"\"{INSUFF_MSG}\". "
    "No inventes datos ni agregues contenido fuera del dominio."
)

# ------------------------ LLM helpers ------------------------
def _ensure_openrouter_env():
    if not os.getenv("OPENAI_API_KEY") and os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    if not os.getenv("OPENAI_BASE_URL") and os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENAI_BASE_URL"] = "https://openrouter.ai/api/v1"

def _make_llm(model_name: Optional[str] = None) -> ChatOpenAI:
    _ensure_openrouter_env()
    model = model_name or os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct")
    max_toks = int(os.getenv("GEN_MAX_TOKENS", "800"))
    return ChatOpenAI(model=model, temperature=0, max_tokens=max_toks)

def _make_light_llm() -> ChatOpenAI:
    model = os.getenv("LLM_QCONDENSE", os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct"))
    return ChatOpenAI(model=model, temperature=0, max_tokens=200)

def _strip_insuff_appendix(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    if t == INSUFF_MSG:
        return t
    if INSUFF_MSG in t:
        t = t.replace(INSUFF_MSG, "").strip()
        t = re.sub(r"\(\s*en caso.*?\)\s*$", "", t, flags=re.IGNORECASE | re.DOTALL).strip()
        t = re.sub(r"\n{3,}", "\n\n", t)
    return t

# ------------------------ Utils comunes ------------------------
# Nota: usamos >=4 para palabras “fuertes” pero el léxico del índice se arma con tokens >=3 (vectorstore),
# lo cual mejora la intersección con abreviaturas tipo 'mail', 'wifi' sin hardcodear sinónimos.
_WORD = re.compile(r"[a-záéíóúüñ0-9]{4,}", re.IGNORECASE)

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na > 0 and nb > 0 else 0.0

def _mentions_docs(text: str) -> bool:
    return bool(re.search(r"\b(documentos?|contexto|extractos?|anexos?)\b", text, re.IGNORECASE))

def _norm(s: str) -> str:
    s = s.lower().strip()
    return ''.join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _has_anchor_terms(question: str, docs: List[Document]) -> bool:
    toks = [t for t in _WORD.findall(_norm(question))]
    if not toks:
        return True
    ctxn = _norm(" ".join(d.page_content for d in docs[:5]))
    return any(t in ctxn for t in toks)

def _semantic_ood(question: str, docs: List[Document]) -> bool:
    if not docs:
        return True
    qv = np.array(dense.embed_query(question))
    ctx = " ".join(d.page_content for d in docs[:5])
    cv = np.array(dense.embed_query(ctx)) if ctx else np.zeros_like(qv)
    sim = _cosine(qv, cv)
    thresh = float(os.getenv("OOD_MIN_SIM", "0.22"))
    return sim < thresh

def _semantic_similarity(q: str, chunk: str) -> float:
    qv = np.array(dense.embed_query(q))
    cv = np.array(dense.embed_query(chunk))
    return _cosine(qv, cv)

# ====== Léxico del corpus + expansión agnóstica (typos/jergas) ======
def _load_vocab(path=os.path.join("indices", "lexicon.json")) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
_VOCAB = _load_vocab()

def _tokens(q: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(q or "")]

def expand_query_corpus_aware(q: str, max_add: int = 6, fuzz_min: int = 82) -> str:
    """
    Añade términos del LÉXICO del corpus similares a tokens de la query (corrige typos),
    de forma completamente agnóstica al dominio.
    """
    if not _VOCAB:
        return q
    toks = _tokens(q)
    extras: list[str] = []
    for t in toks:
        # Tomamos los 3 más parecidos por token; umbral algo más permisivo (>=82)
        for cand, score, _ in process.extract(t, _VOCAB, scorer=fuzz.WRatio, limit=3):
            if score >= fuzz_min:
                extras.append(cand)
    # Dedupe y recorte
    extras = list(dict.fromkeys(extras))[:max_add]
    return q if not extras else (q + " " + " ".join(extras))

# ====== Pseudo-Relevance Feedback (RM3-like) ======
_STOP = {
    "de","del","la","el","los","las","un","una","y","o","u","que","con","en","por","para","como",
    "a","al","lo","su","sus","si","no","se","es","son","ser","esta","este","estos","estas",
    "the","a","an","and","or","of","to","in","for","on","by","is","are","be","this","that","these","those"
}

def _prf_terms_from_docs(docs: list[Document], base_query: str, max_terms: int = 6) -> list[str]:
    if not docs:
        return []
    q_toks = set(_tokens(base_query))
    counts: dict[str, int] = {}
    for d in docs[:6]:
        for t in _tokens(d.page_content):
            if len(t) < 4 or t in _STOP or t in q_toks:
                continue
            counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    terms = [w for w,_ in ranked if (not _VOCAB or w in _VOCAB)][:max_terms]
    return terms

# ------------------------ Follow-ups genéricos ------------------------
_GENERIC_FUPS = (
    "como se hace","cómo se hace","como se prepara","cómo se prepara",
    "instrucciones","y las instrucciones","paso a paso","procedimiento",
    "preparación","preparacion","cómo lo hago","como lo hago",
    "detallame","explícame","explicame","lista","listado",
    "1ra","2da","3ra","primera","segunda","tercera"
)

def _is_generic_followup(q: str) -> bool:
    qn = (q or "").lower().strip()
    return any(p in qn for p in _GENERIC_FUPS)

_NUM_LINE = re.compile(r"^\s*(\d+)[\.)-]\s+(.*)$")
_BULLET   = re.compile(r"^\s*[-•]\s+(.*)$")
_BOLD     = re.compile(r"\*\*([^*]{3,120})\*\*")
_SENT_SPLIT = re.compile(r"(?<=[\.\?\!])\s+")

def _ordinal_from_question(q: str) -> Optional[int]:
    ql = (q or "").lower()
    m = re.search(r"\b(\d+)\s*(?:°|ra|er|º|o|a)?\b", ql)
    if m:
        try: return int(m.group(1))
        except: pass
    if "primera" in ql or "1ra" in ql: return 1
    if "segunda" in ql or "2da" in ql: return 2
    if "tercera" in ql or "3ra" in ql: return 3
    return None

def _last_assistant_text(history: list[dict]) -> str:
    for m in reversed(history or []):
        if m.get("role") == "assistant" and (m.get("content") or "").strip():
            return m["content"].strip()
    return ""

def _split_candidates(base: str) -> list[str]:
    lines = base.splitlines()
    items: list[str] = []

    # 1) Numerados
    current = []; seen_any_num = False
    for ln in lines:
        m = _NUM_LINE.match(ln)
        if m:
            seen_any_num = True
            if current: items.append("\n".join(current).strip()); current = []
            current.append(ln)
        else:
            if seen_any_num: current.append(ln)
    if current: items.append("\n".join(current).strip())

    # 2) Bullets
    current = []
    for ln in lines:
        m = _BULLET.match(ln)
        if m:
            if current: items.append("\n".join(current).strip()); current = []
            current.append(ln)
        else:
            if current: current.append(ln)
    if current: items.append("\n".join(current).strip())

    # 3) Negritas
    for m in _BOLD.finditer(base):
        title = m.group(1).strip()
        if len(title) >= 3: items.append(title)

    # 4) Fallback: ventanas de 2–3 oraciones
    if not items:
        sents = _SENT_SPLIT.split(base.strip())
        win = max(2, int(os.getenv("FOLLOWUP_SENT_WIN", "2")))
        for i in range(0, len(sents), win):
            chunk = " ".join(sents[i:i+win]).strip()
            if len(chunk) >= 40: items.append(chunk)

    # dedupe
    uniq, seen = [], set()
    for it in items:
        it2 = re.sub(r"\s{2,}", " ", it).strip()
        if it2 and it2 not in seen:
            seen.add(it2); uniq.append(it2)
    return uniq[:30]

def _choose_span(base: str, q: str) -> str:
    cands = _split_candidates(base)
    if not cands: return base
    ord_n = _ordinal_from_question(q)
    if ord_n is not None:
        num_blocks = [c for c in cands if _NUM_LINE.match(c.splitlines()[0] if c.splitlines() else "")]
        if num_blocks and 1 <= ord_n <= len(num_blocks):
            return num_blocks[ord_n - 1]
    # si no hay ordinal, elegimos por similitud semántica
    best, best_sim = "", -1.0
    for c in cands:
        sim = _semantic_similarity(q, c)
        if sim > best_sim:
            best_sim, best = sim, c
    thresh = float(os.getenv("FOLLOWUP_MIN_SIM", "0.12"))
    return best if best and best_sim >= thresh else base

def _answer_from_history(question: str, history: list[dict], model_name: Optional[str] = None) -> Tuple[str, list[dict]]:
    base_full = _last_assistant_text(history)
    if not base_full:
        return INSUFF_MSG, []
    span = _choose_span(base_full, question)
    if not span:
        return INSUFF_MSG, []
    llm = _make_llm(model_name)
    msgs = [
        ("system",
         "Responde EXCLUSIVAMENTE en español. Usa SOLO el texto base provisto a continuación como fuente. "
         f"Si no hay suficientes datos, responde exactamente: \"{INSUFF_MSG}\"."),
        ("user",
         f"Texto base:\n{span}\n\n"
         f"Consulta del usuario:\n{question}\n\n"
         "Responde claro y, si corresponde, con pasos.")
    ]
    out = (llm.invoke(msgs).content or "").strip()
    if not out or _mentions_docs(out) or out == INSUFF_MSG:
        return INSUFF_MSG, []
    return out, []

# ------------------------ Builder principal ------------------------
def build_rag(model_name: Optional[str] = None):
    llm = _make_llm(model_name)
    retriever = build_pro_retriever(model_name=model_name or os.getenv("LLM_MODEL", "mistralai/mixtral-8x7b-instruct"))

    def answer_fn(question: str, history: Optional[List[Dict]] = None) -> Tuple[str, List[Dict]]:
        q = (question or "").strip()
        if len(q) < 3:
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        # 0) Si es follow-up genérico, probamos SOLO con historial
        if _is_generic_followup(q):
            out_hist, src_hist = _answer_from_history(q, history or [], model_name)
            if out_hist != INSUFF_MSG:
                return out_hist, src_hist

        # ---- Reescritura agnóstica de la query ----
        # 1) Expansión tolerante a typos guiada por el LÉXICO del corpus (dominio-agnóstica)
        q_expanded = expand_query_corpus_aware(q)

        # 2) Primera pasada de recuperación
        docs_first = retriever.invoke(q_expanded)

        # 3) PRF/RM3: extrae términos característicos de esos docs y re-busca
        prf_terms = _prf_terms_from_docs(
            docs_first, base_query=q, max_terms=int(os.getenv("PRF_TERMS", "6"))
        )
        q_final = q_expanded if not prf_terms else (q_expanded + " " + " ".join(prf_terms))

        # 4) Recuperación definitiva con query expandida + PRF
        docs = retriever.invoke(q_final)

        # Gates de seguridad previos a la generación
        total_len = sum(len(d.page_content) for d in docs)
        min_chars = int(os.getenv("MIN_CONTEXT_CHARS", "10"))
        if (len(docs) < 1) or (total_len < min_chars):
            out_hist, src_hist = _answer_from_history(q, history or [], model_name)
            if out_hist == INSUFF_MSG: registrar_consulta_no_resuelta(q)
            return out_hist, src_hist

        if _semantic_ood(q, docs) or not _has_anchor_terms(q, docs):
            out_hist, src_hist = _answer_from_history(q, history or [], model_name)
            if out_hist == INSUFF_MSG: registrar_consulta_no_resuelta(q)
            return out_hist, src_hist

        # similitud mínima por chunk (corte ANTES del LLM)
        min_sim = float(os.getenv("CHUNK_MIN_SIM", "0.35"))
        best_sim = max((_semantic_similarity(q, d.page_content) for d in docs), default=0.0)
        if best_sim < min_sim:
            out_hist, src_hist = _answer_from_history(q, history or [], model_name)
            if out_hist == INSUFF_MSG: registrar_consulta_no_resuelta(q)
            return out_hist, src_hist

        # 3) Generación
        limit = int(os.getenv("CTX_CHAR_LIMIT", "8000"))
        context = "\n\n".join(d.page_content for d in docs)[:limit]
        msgs = [
            ("system", SYSTEM_PROMPT),
            ("user",
             f"Pregunta del usuario:\n{q}\n\n"
             f"Información relevante:\n{context}\n\n"
             f"Recuerda: si no hay datos suficientes, responde exactamente: \"{INSUFF_MSG}\".")
        ]
        out = (llm.invoke(msgs).content or "").strip()
        out = _strip_insuff_appendix(out)

        # 4) Post-chequeo
        if (not out) or _mentions_docs(out) or out == INSUFF_MSG:
            registrar_consulta_no_resuelta(q)
            return INSUFF_MSG, []

        # 5) Fuentes únicas
        seen, uniq = set(), []
        for d in docs:
            src = d.metadata.get("source", "desconocido")
            page = d.metadata.get("page")
            key = (src, page)
            if key not in seen:
                seen.add(key)
                uniq.append({"archivo": src, "paginas": page} if page is not None else {"archivo": src})

        return out, uniq

    return answer_fn
