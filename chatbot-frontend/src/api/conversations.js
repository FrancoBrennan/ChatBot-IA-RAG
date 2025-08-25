import api from "./axios";

export function crearConversacion(titulo = "Nueva conversación") {
  // Enviamos el titulo como query param o body; aquí uso query para simpleza
  return api
    .post(`/conversaciones/?titulo=${encodeURIComponent(titulo)}`)
    .then((r) => r.data);
}

export function listarConversaciones() {
  return api.get("/conversaciones").then((r) => r.data);
}

export function obtenerConversacion(convId) {
  return api.get(`/conversaciones/${convId}`).then((r) => r.data);
}

export function agregarMensaje(convId, { rol, contenido }) {
  return api
    .post(`/conversaciones/${convId}/mensaje`, { rol, contenido })
    .then((r) => r.data);
}

export function borrarConversacion(convId) {
  return api.delete(`/conversaciones/${convId}`);
}
