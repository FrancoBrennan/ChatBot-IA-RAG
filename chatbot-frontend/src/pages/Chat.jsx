import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/axios";
import Sidebar from "../components/Sidebar";
import { useAuth } from "../context/AuthContext";
import "../styles/Chat.css";

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
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
    if (!text) return;

    const currentConvId = await ensureConversation();

    // pintar mensaje de usuario
    const userMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // guardar mensaje de usuario
    try {
      await api.post(`/conversaciones/${currentConvId}/mensaje`, {
        rol: "user",
        contenido: text,
      });
      // 🔔 backend renombra si es el primer mensaje → pedir al Sidebar refrescar
      window.dispatchEvent(new Event("reload-convs"));
    } catch (err) {
      console.error("No se pudo guardar el mensaje del usuario:", err);
    }

    // pedir respuesta del bot y guardarla
    try {
      const { data } = await api.get("/buscar", { params: { pregunta: text } });
      const botText = data?.respuesta ?? "Sin respuesta.";
      const botMessage = { role: "assistant", content: botText };
      setMessages((prev) => [...prev, botMessage]);

      try {
        await api.post(`/conversaciones/${currentConvId}/mensaje`, {
          rol: "assistant",
          contenido: botText,
        });
      } catch (err) {
        console.error("No se pudo guardar el mensaje del bot:", err);
      }
    } catch (err) {
      console.error("Error /buscar:", err);
      const errorMessage = {
        role: "assistant",
        content: "Error al buscar respuesta.",
      };
      setMessages((prev) => [...prev, errorMessage]);
      try {
        await api.post(`/conversaciones/${currentConvId}/mensaje`, {
          rol: "assistant",
          contenido: errorMessage.content,
        });
      } catch {}
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") handleSend();
  };

  return (
    <div className="layout">
      <Sidebar
        onSelectConversation={handleSelectConversation}
        selectedId={chatId}
      />

      <div className="chat-wrapper">
        <div className="top-bar">
          <div style={{ marginBottom: 20 }}>
            <strong>Usuario:</strong> {user?.username}{" "}
            {user?.is_admin ? "(admin)" : ""}
          </div>
          <div>
            {user?.is_admin && (
              <Link to="/admin" className="nav-button">
                Administrar Datasets
              </Link>
            )}
            <br />
            <button onClick={logout} className="nav-button">
              Cerrar sesión
            </button>
          </div>
        </div>

        <div className="chat-box">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              {msg.content}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-box">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              chatId
                ? "Escribí tu pregunta..."
                : "Escribí para iniciar una nueva conversación"
            }
          />
          <button onClick={handleSend}>Enviar</button>
        </div>
      </div>
    </div>
  );
}

export default Chat;
