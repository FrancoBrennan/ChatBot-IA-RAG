import axios from "axios";
import React, { useState } from "react";

const PdfUploader = () => {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  const handleUpload = async () => {
    if (!file) {
      setStatus("Seleccioná un archivo PDF.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(
        "http://localhost:8000/upload-pdf",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        }
      );
      setStatus("✅ PDF subido exitosamente (ID: " + response.data.id + ")");
    } catch (error) {
      console.error(error);
      setStatus("❌ Error al subir el PDF.");
    }
  };

  return (
    <div style={{ marginBottom: "2rem" }}>
      <h3>Subir PDF</h3>
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setFile(e.target.files[0])}
      />
      <button onClick={handleUpload} style={{ marginLeft: "1rem" }}>
        Subir
      </button>
      <p>{status}</p>
    </div>
  );
};

export default PdfUploader;
