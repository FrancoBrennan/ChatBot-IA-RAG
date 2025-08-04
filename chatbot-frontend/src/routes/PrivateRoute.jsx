import React from "react";
import { Navigate } from "react-router-dom";

function PrivateRoute({ user, children }) {
  if (!user || !user.is_admin) {
    return <Navigate to="/login" />;
  }
  return children;
}

export default PrivateRoute;
