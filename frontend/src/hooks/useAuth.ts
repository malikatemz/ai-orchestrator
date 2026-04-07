/**
 * useAuth Hook
 *
 * Manages authentication state including JWT token storage, user info,
 * and workspace context. Handles login, logout, token refresh, and
 * automatic token invalidation on logout.
 *
 * Features:
 * - JWT token storage in localStorage
 * - User and workspace context
 * - Automatic token refresh
 * - Login/logout functionality
 * - Protected token access
 *
 * @example
 * const { token, user, workspace, login, logout, isAuthenticated } = useAuth();
 */

import { useState, useCallback, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  fullName: string;
  role: string;
}

interface Workspace {
  id: string;
  name: string;
  role: 'owner' | 'admin' | 'operator' | 'viewer';
}

interface AuthContextType {
  token: string | null;
  user: User | null;
  workspace: Workspace | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => void;
}

const STORAGE_KEY_TOKEN = 'auth_token';
const STORAGE_KEY_USER = 'auth_user';
const STORAGE_KEY_WORKSPACE = 'auth_workspace';

export function useAuth(): AuthContextType {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN);
      const storedUser = localStorage.getItem(STORAGE_KEY_USER);
      const storedWorkspace = localStorage.getItem(STORAGE_KEY_WORKSPACE);

      if (storedToken) setToken(storedToken);
      if (storedUser) setUser(JSON.parse(storedUser));
      if (storedWorkspace) setWorkspace(JSON.parse(storedWorkspace));
    } catch (err) {
      console.error('Failed to restore auth state:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Login failed');
      }

      const data = await response.json();
      const { access_token, user, workspace } = data;

      setToken(access_token);
      setUser(user);
      setWorkspace(workspace);

      localStorage.setItem(STORAGE_KEY_TOKEN, access_token);
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
      localStorage.setItem(STORAGE_KEY_WORKSPACE, JSON.stringify(workspace));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      // Notify backend to invalidate token
      if (token) {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        });
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setToken(null);
      setUser(null);
      setWorkspace(null);
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_USER);
      localStorage.removeItem(STORAGE_KEY_WORKSPACE);
    }
  }, [token]);

  const refresh = useCallback(async (): Promise<void> => {
    if (!token) return;

    try {
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const data = await response.json();
      const newToken = data.access_token;

      setToken(newToken);
      localStorage.setItem(STORAGE_KEY_TOKEN, newToken);
    } catch (err) {
      console.error('Token refresh failed:', err);
      await logout();
    }
  }, [token, logout]);

  const switchWorkspace = useCallback((workspaceId: string): void => {
    // In a real app, this would fetch the workspace details and update role
    // For now, just update the workspace ID
    if (workspace) {
      const updated = { ...workspace, id: workspaceId };
      setWorkspace(updated);
      localStorage.setItem(STORAGE_KEY_WORKSPACE, JSON.stringify(updated));
    }
  }, [workspace]);

  return {
    token,
    user,
    workspace,
    isAuthenticated: !!token && !!user,
    isLoading,
    login,
    logout,
    refresh,
    switchWorkspace,
  };
}
