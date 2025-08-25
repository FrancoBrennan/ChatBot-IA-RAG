import api from "./axios";

export function listarUsuarios() {
  return api.get("/admin/users").then((r) => r.data);
}

export function crearUsuario(payload) {
  return api.post("/admin/users", payload).then((r) => r.data);
}

export function cambiarEstadoUsuario(userId, activo) {
  return api
    .patch(`/admin/users/${userId}/estado`, null, { params: { activo } })
    .then((r) => r.data);
}

export function borrarUsuario(userId) {
  return api.delete(`/admin/users/${userId}`);
}
