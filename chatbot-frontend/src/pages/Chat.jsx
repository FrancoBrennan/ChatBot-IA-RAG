import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import "../styles/Chat.css";

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const [chatId, setChatId] = useState(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom(); // ✅ Cada vez que cambian los mensajes, se scrollea abajo
  }, [messages]);

  const handleKeyDown = (e) => {
    if (e == "Enter") handleSend();
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // Guardar mensaje del usuario
    await axios.post(`http://localhost:8000/conversaciones/${chatId}/mensaje`, {
      rol: "user",
      contenido: input,
    });

    try {
      const response = await axios.get("http://localhost:8000/buscar", {
        params: { pregunta: input },
      });

      const botMessage = {
        role: "assistant",
        content: response.data.respuesta,
      };

      // Mostrar y guardar respuesta del bot
      setMessages((prev) => [...prev, botMessage]);

      await axios.post(
        `http://localhost:8000/conversaciones/${chatId}/mensaje`,
        {
          rol: "assistant",
          contenido: response.data.respuesta,
        }
      );
    } catch (err) {
      const errorMessage = {
        role: "assistant",
        content: "Error al buscar respuesta.",
      };

      // Mostrar mensaje de error y guardarlo también
      setMessages((prev) => [...prev, errorMessage]);

      await axios.post(
        `http://localhost:8000/conversaciones/${chatId}/mensaje`,
        {
          rol: "assistant",
          contenido: errorMessage.content,
        }
      );
    }
  };

  const handleSelectConversation = async (id) => {
    setChatId(id);
    try {
      const res = await axios.get(`http://localhost:8000/conversaciones/${id}`);
      //console.log(res);
      const mensajes = res.data.mensajes.map((m) => ({
        role: m.rol,
        content: m.contenido,
      }));
      setMessages(mensajes);
    } catch (err) {
      console.error("Error al cargar mensajes:", err);
    }
  };

  return (
    <div className="layout">
      <Sidebar
        onSelectConversation={handleSelectConversation}
        selectedId={chatId}
      />

      <div className="chat-wrapper">
        <div className="top-bar">
          <button className="nav-button" onClick={() => navigate("/admin")}>
            Administrar Datasets
          </button>
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
            onKeyDown={(e) => handleKeyDown(e.code)}
            placeholder="Escribí tu pregunta..."
          />
          <button onClick={handleSend}>Enviar</button>
        </div>
      </div>
    </div>
  );
}

export default Chat;
