import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import "../styles/Sidebar.css";

function Sidebar({ onSelectConversation, selectedId }) {
  const [conversaciones, setConversaciones] = useState([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const fetchConversaciones = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/conversaciones"); // lista solo las del usuario
      setConversaciones(res.data || []);
    } catch (err) {
      console.error("Error al obtener conversaciones:", err);
      if (err?.response?.status === 401) {
        localStorage.removeItem("token");
        navigate("/login", { replace: true });
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchConversaciones();
    // permitir que otros componentes pidan refresco (ej: tras primer mensaje)
    const reload = () => fetchConversaciones();
    window.addEventListener("reload-convs", reload);
    return () => window.removeEventListener("reload-convs", reload);
  }, [fetchConversaciones]);

  const handleNueva = async () => {
    try {
      // backend aceptará body opcional; envío {} para explicitar POST
      const res = await api.post("/conversaciones/", {});
      // refrescar lista para mantener orden por fecha_creacion
      await fetchConversaciones();
      onSelectConversation(res.data.id);
      localStorage.setItem("activeConvId", String(res.data.id));
      navigate("/chat");
    } catch (err) {
      console.error("No se pudo crear la conversación:", err);
      if (err?.response?.status === 401) {
        localStorage.removeItem("token");
        navigate("/login", { replace: true });
      } else {
        alert("No se pudo crear la conversación");
      }
    }
  };

  return (
    <div className="sidebar">
      <button className="new-conv-button" onClick={handleNueva}>
        + Nueva conversación
      </button>

      {loading ? (
        <div className="conv-empty">Cargando…</div>
      ) : conversaciones.length === 0 ? (
        <div className="conv-empty">Sin conversaciones</div>
      ) : (
        <ul className="conv-list">
          {conversaciones.map((conv) => (
            <li
              key={conv.id}
              className={`conv-item ${selectedId === conv.id ? "active" : ""}`}
              onClick={() => {
                onSelectConversation(conv.id);
                localStorage.setItem("activeConvId", String(conv.id));
                navigate("/chat");
              }}
              title={conv.titulo}
            >
              {conv.titulo || `Conv ${conv.id}`}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default Sidebar;
