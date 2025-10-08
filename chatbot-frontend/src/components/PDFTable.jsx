import PropTypes from "prop-types";
import React from "react";
import "../styles/AdminPanel.css";

/**
 * Tabla de archivos PDF con aspecto “table” y acciones.
 * Usa las clases .table, .table--compact, .btn, .btn-danger definidas en AdminPanel.css
 */
export default function PDFTable({ archivos = [], onDelete, className = "" }) {
  return (
    <table className={`table table--compact ${className}`.trim()}>
      <thead>
        <tr>
          <th className="id-col">ID</th>
          <th className="name-col">Nombre</th>
          <th className="actions-col">Acciones</th>
        </tr>
      </thead>
      <tbody>
        {archivos.map((a) => (
          <tr key={a.id}>
            <td>{a.id}</td>
            <td className="truncate" title={a.nombre}>
              {a.nombre}
            </td>
            <td>
              <div className="actions">
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => onDelete?.(a.id)}
                >
                  Eliminar
                </button>
              </div>
            </td>
          </tr>
        ))}

        {archivos.length === 0 && (
          <tr>
            <td colSpan={3}>Sin archivos</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

PDFTable.propTypes = {
  archivos: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
      nombre: PropTypes.string.isRequired,
    })
  ),
  onDelete: PropTypes.func,
  className: PropTypes.string,
};
