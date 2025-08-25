import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import AdminPanel from "./pages/AdminPanel";
import Chat from "./pages/Chat";
import Login from "./pages/Login";
import PrivateRoute from "./routes/PrivateRoute";

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          {/* Redirige raíz a /chat */}
          <Route path="/" element={<Navigate to="/chat" replace />} />

          {/* Login público; si ya hay sesión, mandá a /chat */}
          <Route
            path="/login"
            element={
              localStorage.getItem("token") ? (
                <Navigate to="/chat" replace />
              ) : (
                <Login />
              )
            }
          />

          {/* Chat: requiere estar logueado */}
          <Route
            path="/chat"
            element={
              <PrivateRoute>
                <Chat />
              </PrivateRoute>
            }
          />

          {/* Admin: requiere estar logueado y ser admin */}
          <Route
            path="/admin"
            element={
              <PrivateRoute adminOnly>
                <AdminPanel />
              </PrivateRoute>
            }
          />

          {/* 404 básico */}
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
