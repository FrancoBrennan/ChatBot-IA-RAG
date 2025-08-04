// src/components/Sidebar.jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "../api/axios";
import "../styles/Sidebar.css";

function Sidebar({ onSelectConversation, selectedId }) {
  const [conversaciones, setConversaciones] = useState([]);

  const navigate = useNavigate();

  useEffect(() => {
    fetchConversaciones();
  }, []);

  const fetchConversaciones = async () => {
    const res = await axios.get("/conversaciones");
    setConversaciones(res.data);
  };

  const handleNueva = async () => {
    const res = await axios.post("/conversaciones");
    setConversaciones((prev) => [...prev, res.data]);
    onSelectConversation(res.data.id);
    navigate("/chat");
  };

  return (
    <div className="sidebar">
      <button className="new-conv-button" onClick={handleNueva}>
        + Nueva conversación
      </button>
      <ul className="conv-list">
        {conversaciones.map((conv) => (
          <li
            key={conv.id}
            className={`conv-item ${selectedId === conv.id ? "active" : ""}`}
            onClick={() => {
              onSelectConversation(conv.id);
              navigate("/chat");
            }}
          >
            {conv.titulo}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Sidebar;
