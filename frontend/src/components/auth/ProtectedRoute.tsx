/**
 * Protected Route Wrapper Component
 * Enforces authentication and authorization for routes
 * Phase 5: Frontend Auth Integration
 */

import React, { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthContext } from "@/hooks/useAuth";
import { Role, Permission } from "@/lib/auth";
import LoadingSpinner from "@/components/common/LoadingSpinner";

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: Role;
  requiredPermissions?: Permission[];
  fallbackRoute?: string;
}

/**
 * ProtectedRoute Component
 * Wraps components to enforce authentication and role-based access
 *
 * Usage:
 * <ProtectedRoute requiredRole={Role.ADMIN} requiredPermissions={[Permission.MANAGE_USERS]}>
 *   <AdminPanel />
 * </ProtectedRoute>
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
  requiredPermissions = [],
  fallbackRoute = "/login",
}) => {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, hasPermission, isLoading } = useAuthContext();
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Avoid hydration mismatch
  if (!isMounted || isLoading) {
    return <LoadingSpinner />;
  }

  // Check if user is authenticated
  if (!isAuthenticated) {
    // Store the attempted route for post-login redirect
    if (typeof window !== "undefined") {
      sessionStorage.setItem("redirectTo", pathname);
    }
    router.push(fallbackRoute);
    return <LoadingSpinner />;
  }

  // Check if user has required role
  if (requiredRole && (!user || user.role !== requiredRole)) {
    // If role is stricter requirement (Owner > Admin > Member > Viewer)
    const roleHierarchy = {
      [Role.OWNER]: 4,
      [Role.ADMIN]: 3,
      [Role.MEMBER]: 2,
      [Role.VIEWER]: 1,
      [Role.BILLING_ADMIN]: 3, // Equal to Admin for most purposes
    };

    const userRoleLevel = user ? roleHierarchy[user.role] || 0 : 0;
    const requiredRoleLevel = roleHierarchy[requiredRole] || 0;

    if (userRoleLevel < requiredRoleLevel) {
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Access Denied
            </h1>
            <p className="text-gray-600 mb-4">
              You don't have permission to access this page.
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      );
    }
  }

  // Check if user has required permissions
  if (requiredPermissions.length > 0) {
    const hasAllPermissions = requiredPermissions.every((permission) =>
      hasPermission(permission)
    );

    if (!hasAllPermissions) {
      return (
        <div className="flex items-center justify-center h-screen">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Insufficient Permissions
            </h1>
            <p className="text-gray-600 mb-4">
              You don't have the required permissions for this action.
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
};

export default ProtectedRoute;
