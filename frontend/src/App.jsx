import React from "react";
import ChatBot from "./components/ChatBot";
import PdfUploader from "./components/PdfUploader";

function App() {
  return (
    <div
      style={{ maxWidth: "900px", margin: "2rem auto", fontFamily: "Arial" }}
    >
      <h1>📚 Chatbot Tesis</h1>
      <PdfUploader />
      <hr />
      <ChatBot />
    </div>
  );
}

export default App;
