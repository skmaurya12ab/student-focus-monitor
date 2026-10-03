# Authentication & Account Architecture

This document defines the authentication foundation, Google OAuth 2.0 / OpenID Connect integration, secure HttpOnly-cookie session management, and the dedicated Account page established in **Phase 5**.

---

## 1. Authentication Overview

The **Student Focus Monitor** employs **Google OAuth 2.0 / OpenID Connect (OIDC)** as its primary identity provider. Authentication maps external Google identities directly to local users in PostgreSQL while maintaining privacy-first guarantees.

```
                   Google
                     │
                     │ OAuth 2.0 / OIDC Flow
                     ▼
               FastAPI Backend (/api/auth/google)
                     │
             identity verification
                     │
                     ▼
                 PostgreSQL
                 /        \
                /          \
             users     auth_identities
                │
                ▼
          authenticated user
                │
                ▼
     application session (HttpOnly cookie)
                │
                ▼
            React frontend
                │
          ┌─────┴─────┐
          ▼           ▼
      Dashboard     Account
```

---

## 2. Security & Session Model

- **Session Format**: Signed JSON Web Token (JWT) using HMAC-SHA256 (`HS256`).
- **Token Claims**:
  - `sub`: User UUID string (matching `users.id`).
  - `iat`: Timestamp of issuance.
  - `exp`: Expiration timestamp (default 7 days).
- **Transport**: Secure `HttpOnly` cookie (`sfm_session`) with `SameSite=lax` and `Path=/`.
- **Client Security**: No tokens or sensitive authentication credentials are stored in `localStorage` or accessible to browser JavaScript, mitigating XSS token-theft risks.
- **Fallback Support**: `Authorization: Bearer <token>` header is supported as a secondary fallback for programmatic CLI tools or tests.

---

## 3. Authoritative External Identity & Merge Prevention

- **Authoritative Identity**: The tuple `(provider, provider_subject)` is the sole authoritative external identifier.
- **No Automatic Email Linking**: An incoming Google authentication with a new `provider_subject` will **never** automatically link to or merge with an existing user record based on matching email address.
- **Conflict Handling**: If an authentication attempt provides a new subject ID with an email that is already registered to another user, the backend rejects the request with `409 Conflict` to prevent identity confusion and account takeover.
- **Privacy Boundary**: `provider_subject` is an internal identifier stored in PostgreSQL but is intentionally omitted from user-facing Account API responses and dashboard displays.

---

## 4. Database Integration (Phase 4 Schema)

Authentication integrates directly with the existing Phase 4 tables:

1. **`users` Table**:
   - `id`: UUID primary key.
   - `display_name`: Student display name (editable).
   - `email`: User email address (unique index).
   - `is_active`: Boolean active status.
   - `created_at` & `updated_at`: UTC timestamps.

2. **`auth_identities` Table**:
   - `id`: UUID primary key.
   - `user_id`: Foreign key to `users.id` with `CASCADE` delete.
   - `provider`: Set to `'google'` (enforced by DB check constraint).
   - `provider_subject`: Google subject ID (`sub`).
   - `provider_email`: Google account email.
   - `last_login_at`: Timestamp updated on each successful login.
   - Constraint: `uq_auth_identities_provider_subject` guarantees 1:1 identity linkage.

3. **`user_settings` Table**:
   - Automatically created with default alert persistence thresholds on first student registration.

---

## 5. API Endpoints

### Authentication Routes (`/api/auth`)

| Method | Endpoint | Description | Session Transport |
|---|---|---|---|
| `GET` | `/api/auth/google/url` | Generates Google OAuth authorization URL with CSRF state token | None |
| `POST` | `/api/auth/google` | Verifies Google ID token or code, provisions user, sets session cookie | HttpOnly Cookie |
| `POST` | `/api/auth/dev-login` | Mock authentication for development and testing, sets session cookie | HttpOnly Cookie |
| `GET` | `/api/auth/me` | Returns current authenticated user profile | Cookie (or Bearer fallback) |
| `POST` | `/api/auth/logout` | Terminates active session and clears session cookie | Cookie |

### Account Routes (`/api/account`)

| Method | Endpoint | Description | Session Transport |
|---|---|---|---|
| `GET` | `/api/account` | Retrieves full account details and linked Google identities (excluding subject ID) | Cookie |
| `PATCH` | `/api/account` | Updates editable profile fields (`display_name`) with validation | Cookie |

---

## 6. Account Page vs. Settings Page

To maintain a clean separation of concerns:

- **Settings Page (`/settings`)**:
  - Alert Thresholds (delays for 6 canonical distraction types)
  - Alerts & Notifications (sound, banner, session summary)
  - Webcam Device & Quality Selection
  - Profile preview card with link to Account management

- **Account Page (`/account`)**:
  - Profile information (avatar, display name, account status)
  - Editable display name with validation and instant feedback
  - Google Authentication connection status, verified email, and last login time
  - Session security details (Secure HttpOnly cookie session) and active monitoring count
  - Account Sign Out action

