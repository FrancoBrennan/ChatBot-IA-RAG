import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import AdminPanel from "./pages/AdminPanel";
import Chat from "./pages/Chat";
import Login from "./pages/Login";
// import PrivateRoute from "./routes/PrivateRoute"; //
// import { useAuth } from "./context/AuthContext"; //

function App() {
  // const { user } = useAuth(); //

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
