import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/axios";
import Sidebar from "../components/Sidebar";
import { useAuth } from "../context/AuthContext";
import "../styles/Chat.css";

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const [chatId, setChatId] = useState(() => {
    const saved = localStorage.getItem("activeConvId");
    return saved ? Number(saved) : null;
  });
  const { user, logout } = useAuth();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // cargar mensajes de una conversación seleccionada (desde Sidebar)
  const handleSelectConversation = async (id) => {
    setChatId(id);
    localStorage.setItem("activeConvId", String(id));
    try {
      const res = await api.get(`/conversaciones/${id}`);
      const msgs = (res.data.mensajes || []).map((m) => ({
        role: m.rol,
        content: m.contenido,
      }));
      setMessages(msgs);
    } catch (err) {
      console.error("Error al cargar mensajes:", err);
      setMessages([]);
    }
  };

  // fallback: si el usuario escribe sin conversación activa, crea una primero
  const ensureConversation = async () => {
    if (chatId) return chatId;
    const { data } = await api.post("/conversaciones/", {}); // crea conv vacía
    setChatId(data.id);
    localStorage.setItem("activeConvId", String(data.id));
    setMessages([]);
    return data.id;
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;

    setSending(true);
    const currentConvId = await ensureConversation();

    // UI optimista: mostrar mensaje del usuario
    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    try {
      const { data } = await api.post(`/conversaciones/${currentConvId}/mensaje`, {
        rol: "user",
        contenido: text,
      });

      let botText = data?.respuesta ?? "Sin respuesta.";
      const sources = Array.isArray(data?.fuentes) ? data.fuentes : [];
      // Fallback: si el backend no incluyó “Basado en:” y sí hay fuentes, lo agregamos acá.
      if (!/Basado en:/i.test(botText) && sources.length > 0) {
        botText = `${botText}\n\nBasado en: ${sources.join(", ")}`;
      }
      setMessages((prev) => [...prev, { role: "assistant", content: botText }]);

      // actualizar título si es primer mensaje
      window.dispatchEvent(new Event("reload-convs"));
    } catch (err) {
      console.error("Error enviando mensaje:", err);
      if (err?.response?.status === 401) {
        logout();
        return;
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Error al generar respuesta." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !sending) handleSend();
  };

  return (
    <div className="layout">
      <Sidebar
        onSelectConversation={handleSelectConversation}
        selectedId={chatId}
      />

      <div className="chat-wrapper">
        <div className="top-bar">
          <div className="user-info">
            <strong>Usuario:</strong> {user?.username}{" "}
            {user?.is_admin ? "(admin)" : ""}
          </div>

          {user?.is_admin && (
            <Link to="/admin" className="nav-button topbar-btn">
              Administrar Datasets
            </Link>
          )}

          <button onClick={logout} className="nav-button topbar-btn">
            Cerrar sesión
          </button>
        </div>

        <div className="chat-box">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              <div style={{ whiteSpace: "pre-wrap" }}>{msg.content}</div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-box">
          <input
            //type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            placeholder={
              chatId
                ? "Escribí tu pregunta..."
                : "Escribí para iniciar una nueva conversación"
            }
          />
          <button onClick={handleSend} disabled={sending}>
            {sending ? "Enviando…" : "Enviar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default Chat;
