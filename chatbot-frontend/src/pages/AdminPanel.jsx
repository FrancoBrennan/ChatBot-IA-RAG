import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  borrarUsuario,
  cambiarEstadoUsuario,
  crearUsuario,
  listarUsuarios,
} from "../api/adminUsers";
import axios from "../api/axios";
import PDFTable from "../components/PDFTable";

import "../styles/AdminPanel.css";

function AdminPanel() {
  const [archivos, setArchivos] = useState([]);
  const [file, setFile] = useState(null);
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({
    username: "",
    password: "",
    nombre: "",
    is_admin: false,
    activo: true,
  });
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const fetchArchivos = async () => {
    const res = await axios.get("/listar-datasets");
    setArchivos(res.data);
  };

  async function load() {
    const data = await listarUsuarios();
    setUsers(data);
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    fetchArchivos();
  }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await crearUsuario(form);
      setForm({
        username: "",
        password: "",
        nombre: "",
        is_admin: false,
        activo: true,
      });
      await load();
      alert("Usuario creado");
    } catch (err) {
      if (err?.response?.status === 409) setError("El usuario ya existe");
      else setError("Error al crear usuario");
    }
  }

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

      <div style={{ padding: 16 }}>
        <h2>Panel de Administración</h2>

        <section style={{ marginTop: 16 }}>
          <h3>Crear usuario</h3>
          <form
            onSubmit={handleCreate}
            style={{ display: "grid", gap: 8, maxWidth: 360 }}
          >
            <input
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required
            />
            <input
              placeholder="Nombre (opcional)"
              value={form.nombre}
              onChange={(e) => setForm({ ...form, nombre: e.target.value })}
            />
            <input
              type="password"
              placeholder="Contraseña"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
            <label>
              <input
                type="checkbox"
                checked={form.is_admin}
                onChange={(e) =>
                  setForm({ ...form, is_admin: e.target.checked })
                }
              />{" "}
              Admin
            </label>
            <label>
              <input
                type="checkbox"
                checked={form.activo}
                onChange={(e) => setForm({ ...form, activo: e.target.checked })}
              />{" "}
              Activo
            </label>
            {error && <p style={{ color: "red" }}>{error}</p>}
            <button type="submit">Crear</button>
          </form>
        </section>

        <section style={{ marginTop: 24 }}>
          <h3>Usuarios</h3>
          <table
            border="1"
            cellPadding="6"
            style={{ borderCollapse: "collapse", width: "100%", maxWidth: 720 }}
          >
            <thead>
              <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Nombre</th>
                <th>Admin</th>
                <th>Activo</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>{u.nombre || "-"}</td>
                  <td>{u.is_admin ? "Sí" : "No"}</td>
                  <td>{u.activo ? "Sí" : "No"}</td>
                  <td style={{ display: "flex", gap: 8 }}>
                    <button
                      onClick={async () => {
                        await cambiarEstadoUsuario(u.id, !u.activo);
                        load();
                      }}
                    >
                      {u.activo ? "Desactivar" : "Activar"}
                    </button>
                    <button
                      onClick={async () => {
                        if (confirm("¿Eliminar usuario?")) {
                          await borrarUsuario(u.id);
                          load();
                        }
                      }}
                    >
                      Borrar
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan="6">Sin usuarios</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

export default AdminPanel;
