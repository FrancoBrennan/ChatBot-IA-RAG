import React from "react";

function ChatMessage({ role, content }) {
  return (
    <div className={`message ${role}`}>
      <strong>{role === "user" ? "Vos" : "Asistente"}:</strong> {content}
    </div>
  );
}

export default ChatMessage;
