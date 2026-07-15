import { Navigate, Outlet } from "react-router-dom";

import type { Role } from "../api/types";
import { useAuthStore } from "../stores/authStore";

interface RequireRoleProps {
  roles: Role[];
}

export function RequireRole({ roles }: RequireRoleProps) {
  const role = useAuthStore((state) => state.user?.role);

  if (!role || !roles.includes(role)) {
    return <Navigate to="/forbidden" replace />;
  }

  return <Outlet />;
}
