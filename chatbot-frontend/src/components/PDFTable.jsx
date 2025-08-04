import React from "react";
import "../styles/AdminPanel.css";

function PDFTable({ archivos, onDelete }) {
  return (
    <table className="pdf-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Nombre</th>
          <th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        {archivos.map((doc) => (
          <tr key={doc.id}>
            <td>{doc.id}</td>
            <td>{doc.nombre}</td>
            <td>
              <button onClick={() => onDelete(doc.id)}>Eliminar</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default PDFTable;
