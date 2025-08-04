import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import AdminPanel from "./pages/AdminPanel";
import Chat from "./pages/Chat";
import Login from "./pages/Login";
// import PrivateRoute from "./routes/PrivateRoute"; // 🔴 comentá esta línea si ya no la usás
// import { useAuth } from "./context/AuthContext"; // 🔴 idem si no se usa

function App() {
  // const { user } = useAuth(); // 🔴 comentá esto también

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/login" element={<Login />} />
        {/* ACCESO DIRECTO al AdminPanel sin autenticación */}
        <Route path="/admin" element={<AdminPanel />} />
      </Routes>
    </Router>
  );
}

export default App;
