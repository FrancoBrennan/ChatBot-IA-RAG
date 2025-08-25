import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function PrivateRoute({ children, adminOnly = false }) {
  const { user } = useAuth();
  const token = localStorage.getItem("token");

  if (!token) return <Navigate to="/login" replace />;
  if (adminOnly && user && !user.is_admin) return <Navigate to="/" replace />;

  return children;
}
