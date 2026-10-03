import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { AuthUser } from '../types/auth';
import {
  fetchCurrentUser,
  loginWithGoogle,
  devLogin,
  logoutUser,
  updateAccountProfile,
} from '../services/authApi';

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  loginGoogle: (payload: { id_token?: string; code?: string; state?: string }) => Promise<void>;
  loginDev: (email?: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  updateProfileName: (displayName: string) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Default mock student for instant offline or initial rendering fallback
const DEFAULT_FALLBACK_USER: AuthUser = {
  id: '00000000-0000-0000-0000-000000000001',
  displayName: 'Saurabh Kumar',
  email: 'saurabh@example.com',
  isActive: true,
  createdAt: '2026-08-17T08:00:00Z',
  updatedAt: '2026-08-17T08:00:00Z',
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(DEFAULT_FALLBACK_USER);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refreshUser = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
    } catch {
      // If unauthenticated or offline, retain fallback user for offline dashboard viewing
      setUser(DEFAULT_FALLBACK_USER);
    } finally {
      setIsLoading(false);
    }
  }, []);


  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const loginGoogle = async (payload: { id_token?: string; code?: string; state?: string }) => {
    try {
      setIsLoading(true);
      setError(null);
      const authenticatedUser = await loginWithGoogle(payload);
      setUser(authenticatedUser);
    } catch (err: any) {
      setError(err.message || 'Google authentication failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const loginDev = async (email?: string, displayName?: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const authenticatedUser = await devLogin({ email, display_name: displayName });
      setUser(authenticatedUser);
    } catch (err: any) {
      setError(err.message || 'Dev login failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      await logoutUser();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const updateProfileName = async (displayName: string) => {
    try {
      setError(null);
      const updated = await updateAccountProfile(displayName);
      setUser(updated);
    } catch (err: any) {
      setError(err.message || 'Failed to update profile');
      throw err;
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user && user.id !== '00000000-0000-0000-0000-000000000001',
        isLoading,
        error,
        loginGoogle,
        loginDev,
        logout,
        updateProfileName,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
