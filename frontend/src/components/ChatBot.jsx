import axios from "axios";
import React, { useState } from "react";

const ChatBot = () => {
  const [pregunta, setPregunta] = useState("");
  const [respuesta, setRespuesta] = useState("");
  const [loading, setLoading] = useState(false);

  const handlePregunta = async () => {
    if (!pregunta) return;
    setLoading(true);
    setRespuesta("");

    try {
      const res = await axios.get("http://localhost:8000/buscar", {
        params: { pregunta },
      });
      console.log("asdasd", res.data);
      setRespuesta(res.data.respuesta || "No se encontró una respuesta.");
    } catch (error) {
      console.error(error);
      setRespuesta("❌ Error al procesar la pregunta.");
    }
    setLoading(false);
  };

  return (
    <div>
      <h3>Consultá al chatbot</h3>
      <input
        type="text"
        value={pregunta}
        onChange={(e) => setPregunta(e.target.value)}
        placeholder="Ej: ¿Cómo configuro el WiFi?"
        style={{ width: "60%", padding: "0.5rem", marginRight: "1rem" }}
      />
      <button onClick={handlePregunta} disabled={loading}>
        {loading ? "Buscando..." : "Preguntar"}
      </button>
      {respuesta && (
        <div
          style={{
            marginTop: "1rem",
            background: "#eee",
            padding: "1rem",
            borderRadius: "8px",
          }}
        >
          <strong>Respuesta:</strong>
          <p>{respuesta}</p>
        </div>
      )}
    </div>
  );
};

export default ChatBot;
