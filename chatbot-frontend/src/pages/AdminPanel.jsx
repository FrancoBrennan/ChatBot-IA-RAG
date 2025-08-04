import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "../api/axios";
import PDFTable from "../components/PDFTable";
import "../styles/AdminPanel.css";

function AdminPanel() {
  const [archivos, setArchivos] = useState([]);
  const [file, setFile] = useState(null);
  const navigate = useNavigate();

  const fetchArchivos = async () => {
    const res = await axios.get("/listar-datasets");
    setArchivos(res.data);
  };

  useEffect(() => {
    fetchArchivos();
  }, []);

  const handleUpload = async () => {
    if (!file || file.type !== "application/pdf") {
      alert("Solo se permiten archivos PDF");
      return;
    }
    const formData = new FormData();
    formData.append("archivo", file);
    await axios.post("/upload", formData);
    setFile(null);
    fetchArchivos();
  };

  const handleDelete = async (id) => {
    await axios.delete(`/eliminar-dataset/${id}`);
    fetchArchivos();
  };

  return (
    <div className="admin-panel">
      <div className="top-bar">
        <button className="nav-button" onClick={() => navigate("/chat")}>
          Volver al Chat
        </button>
      </div>
      <h2>Gestión de Datasets PDF</h2>
      <div className="upload-box">
        <input type="file" onChange={(e) => setFile(e.target.files[0])} />
        <button onClick={handleUpload}>Subir PDF</button>
      </div>
      <PDFTable archivos={archivos} onDelete={handleDelete} />
    </div>
  );
}

export default AdminPanel;
