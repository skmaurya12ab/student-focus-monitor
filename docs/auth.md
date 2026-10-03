# Authentication & Account Architecture

This document defines the authentication foundation, Google OAuth 2.0 / OpenID Connect integration, session management, and the dedicated Account page established in **Phase 5**.

---

## 1. Authentication Overview

The **Student Focus Monitor** employs **Google OAuth 2.0 / OpenID Connect (OIDC)** as its initial identity provider. Authentication maps external Google identities directly to local users in PostgreSQL while maintaining privacy-first guarantees.

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
     application session (JWT Bearer)
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

- **Session Format**: JSON Web Token (JWT) signed using HMAC-SHA256 (`HS256`).
- **Token Claims**:
  - `sub`: User UUID string (matching `users.id`).
  - `iat`: Timestamp of issuance.
  - `exp`: Expiration timestamp (default 7 days).
- **Transport**: Standard `Authorization: Bearer <token>` HTTP header.
- **Client Storage**: Secure local browser storage (`sfm_access_token`).

---

## 3. Database Integration (Phase 4 Schema)

Authentication integrates directly with the existing Phase 4 tables:

1. **`users` Table**:
   - `id`: UUID primary key.
   - `display_name`: Student display name (editable).
   - `email`: User email address.
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

## 4. API Endpoints

### Authentication Routes (`/api/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/auth/google/url` | Generates Google OAuth authorization URL with CSRF state token | No |
| `POST` | `/api/auth/google` | Verifies Google ID token or code, provisions user, returns JWT | No |
| `POST` | `/api/auth/dev-login` | Mock authentication for development and automated testing | No |
| `GET` | `/api/auth/me` | Returns current authenticated user profile | Yes (Bearer) |
| `POST` | `/api/auth/logout` | Terminates active application session | Yes (Bearer) |

### Account Routes (`/api/account`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/account` | Retrieves full account details, linked Google identity, and stats | Yes (Bearer) |
| `PATCH` | `/api/account` | Updates editable profile fields (`display_name`) with validation | Yes (Bearer) |

---

## 5. Account Page vs. Settings Page

To maintain a clean separation of concerns:

- **Settings Page (`/settings`)**:
  - Alert Thresholds (delays for 6 canonical distraction types)
  - Alerts & Notifications (sound, banner, session summary)
  - Webcam Device & Quality Selection
  - Profile preview card with link to Account management

- **Account Page (`/account`)**:
  - Profile information (avatar, display name, account status)
  - Editable display name with validation and instant feedback
  - Google Authentication connection status, subject ID, and linked email
  - Session security details and active monitoring count
  - Account Sign Out action
