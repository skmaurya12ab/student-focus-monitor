/**
 * Authentication and Account TypeScript definitions for Phase 5.
 */

export interface AuthUser {
  id: string;
  displayName: string;
  email: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AuthIdentity {
  id: string;
  provider: string;
  providerEmail: string | null;
  createdAt: string;
  lastLoginAt: string | null;
}

export interface AccountDetails {
  user: AuthUser;
  identities: AuthIdentity[];
  activeSessionsCount: number;
}

export interface AuthSessionResponse {
  status: string;
  user: {
    id: string;
    display_name: string;
    email: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };
}

export interface GoogleAuthUrlResponse {
  url: string;
  state: string;
}
