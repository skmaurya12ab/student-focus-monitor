import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { fetchAccountDetails } from '../../services/authApi';
import { AccountDetails } from '../../types/auth';
import { ExportCloverIcon, GoogleGIcon } from '../../components/common/Icons';

export const AccountPage: React.FC = () => {
  const { user, updateProfileName, logout } = useAuth();
  const [accountDetails, setAccountDetails] = useState<AccountDetails | null>(null);
  const [displayNameInput, setDisplayNameInput] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState<boolean>(false);

  useEffect(() => {
    if (user) {
      setDisplayNameInput(user.displayName);
    }
  }, [user]);

  useEffect(() => {
    let isMounted = true;
    const loadDetails = async () => {
      try {
        const details = await fetchAccountDetails();
        if (isMounted) {
          setAccountDetails(details);
        }
      } catch {
        // Fall back gracefully if unauthenticated or offline
      }
    };

    loadDetails();
    return () => {
      isMounted = false;
    };
  }, [user]);

  const handleSaveName = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = displayNameInput.trim();
    if (!trimmed) {
      setSaveError('Display name cannot be empty');
      return;
    }

    try {
      setIsSaving(true);
      setSaveError(null);
      await updateProfileName(trimmed);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update display name');
    } finally {
      setIsSaving(false);
    }
  };

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await logout();
    } finally {
      setIsLoggingOut(false);
    }
  };

  const avatarInitial = user?.displayName ? user.displayName.charAt(0).toUpperCase() : 'S';
  const emailDisplay = user?.email || 'saurabh@example.com';
  const googleIdentity = accountDetails?.identities.find((id) => id.provider === 'google');
  const memberSince = user?.createdAt
    ? new Date(user.createdAt).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : 'Aug 17, 2026';
  const lastLogin = googleIdentity?.lastLoginAt
    ? new Date(googleIdentity.lastLoginAt).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : 'Today';

  return (
    <div className="sfm-page sfm-account-page" id="account-page">
      {/* Page Header */}
      <header className="sfm-page-header">
        <div className="sfm-header-left">
          <div className="sfm-avatar-circle" aria-label="User Avatar">
            <span>{avatarInitial}</span>
          </div>
          <div className="sfm-header-titles">
            <h1 className="sfm-page-title">Account & Identity</h1>
            <p className="sfm-page-subtitle">
              Manage personal profile details, Google authentication, and security preferences.
            </p>
          </div>
        </div>

        <div className="sfm-header-right">
          <div className="sfm-session-status-badge" aria-label="Current session state">
            <span className="sfm-status-dot-active" />
            <span>{user ? 'Session Active' : 'Offline'}</span>
          </div>

          <button
            type="button"
            className="sfm-icon-btn"
            aria-label="Export account info"
            title="Export account info"
          >
            <ExportCloverIcon size={18} />
          </button>
        </div>
      </header>

      {/* Content Grid */}
      <div className="sfm-content-grid">
        {/* Card 1: Profile Information & Editable Fields */}
        <section
          className="sfm-card sfm-card-full sfm-account-profile-card"
          aria-labelledby="account-profile-heading"
        >
          <div className="sfm-card-header">
            <h2 id="account-profile-heading" className="sfm-card-heading">
              Profile Information
            </h2>
            <p className="sfm-card-subheading">
              Personal credentials and student identity visible across your dashboard
            </p>
          </div>

          <div className="sfm-account-profile-body">
            <div className="sfm-account-avatar-column">
              <div className="sfm-profile-avatar-large" aria-label="Profile Initial">
                <span>{avatarInitial}</span>
              </div>
              <div className="sfm-account-tags">
                <span className="sfm-tag-student">Student Account</span>
                <span className="sfm-tag-status">Active</span>
              </div>
            </div>

            <form onSubmit={handleSaveName} className="sfm-account-edit-form">
              <div className="sfm-form-row">
                <div className="sfm-form-field">
                  <label htmlFor="account-display-name-input" className="sfm-input-label">
                    Display Name
                  </label>
                  <div className="sfm-input-action-group">
                    <input
                      id="account-display-name-input"
                      type="text"
                      className="sfm-text-input"
                      value={displayNameInput}
                      onChange={(e) => setDisplayNameInput(e.target.value)}
                      maxLength={100}
                      placeholder="Enter student display name"
                      aria-required="true"
                    />
                    <button
                      type="submit"
                      className="sfm-btn-save-changes"
                      id="btn-save-account-name"
                      disabled={isSaving || !displayNameInput.trim()}
                    >
                      {saveSuccess ? 'Saved ✓' : isSaving ? 'Saving...' : 'Save changes'}
                    </button>
                  </div>
                  {saveError && <p className="sfm-field-error">{saveError}</p>}
                </div>
              </div>

              <div className="sfm-form-row sfm-form-row-compact">
                <div className="sfm-form-field">
                  <span className="sfm-input-label">Primary Account Email</span>
                  <div className="sfm-email-verified-box">
                    <span className="sfm-email-value">{emailDisplay}</span>
                    <span className="sfm-badge-verified">✓ Google Verified</span>
                  </div>
                </div>

                <div className="sfm-form-field">
                  <span className="sfm-input-label">Member Since</span>
                  <span className="sfm-static-value">{memberSince}</span>
                </div>
              </div>
            </form>
          </div>
        </section>

        {/* 2-Column Row: Google Auth Identity | Security & Sessions */}
        <div className="sfm-two-col-row">
          {/* Card 2: Google Authentication Information */}
          <section
            className="sfm-card sfm-col-card sfm-google-card"
            aria-labelledby="google-auth-heading"
          >
            <h2 id="google-auth-heading" className="sfm-card-heading">
              Google Authentication
            </h2>
            <p className="sfm-card-subheading">Connected OpenID Connect identity provider</p>

            <div className="sfm-identity-list">
              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Identity Provider</span>
                <div className="sfm-provider-tag">
                  <GoogleGIcon size={16} />
                  <span>Google OAuth 2.0</span>
                </div>
              </div>

              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Linked Google Account</span>
                <span className="sfm-identity-value">{emailDisplay}</span>
              </div>

              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Last Identity Verification</span>
                <span className="sfm-identity-value">{lastLogin}</span>
              </div>

              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Verification Status</span>
                <span className="sfm-badge-verified">Linked & Verified</span>
              </div>
            </div>
          </section>

          {/* Card 3: Session & Privacy Security */}
          <section
            className="sfm-card sfm-col-card sfm-security-card"
            aria-labelledby="session-security-heading"
          >
            <h2 id="session-security-heading" className="sfm-card-heading">
              Session & Security
            </h2>
            <p className="sfm-card-subheading">Authentication protocol and privacy guarantees</p>

            <div className="sfm-identity-list">
              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Session Protection</span>
                <span className="sfm-identity-value">Secure HttpOnly Cookie</span>
              </div>

              <div className="sfm-identity-item">
                <span className="sfm-identity-label">Active Monitoring Sessions</span>
                <span className="sfm-identity-value">
                  {accountDetails?.activeSessionsCount || 0} active
                </span>
              </div>

              <div className="sfm-privacy-box">
                <strong className="sfm-privacy-title">🔒 Privacy-First Guarantee:</strong>
                <p className="sfm-privacy-desc">
                  Live webcam frames are analyzed entirely in volatile memory and immediately discarded.
                  Raw video is never recorded or stored in the database.
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Card 4: Logout / Account Actions */}
        <section
          className="sfm-card sfm-card-full sfm-account-actions-card"
          aria-labelledby="account-actions-heading"
        >
          <div className="sfm-account-actions-content">
            <div className="sfm-actions-info">
              <h2 id="account-actions-heading" className="sfm-card-heading">
                Account Actions
              </h2>
              <p className="sfm-card-subheading">
                Sign out of your active session or switch student accounts on this device.
              </p>
            </div>

            <div className="sfm-actions-btns">
              <button
                type="button"
                className="sfm-btn-logout"
                id="btn-account-logout"
                onClick={handleLogout}
                disabled={isLoggingOut}
              >
                {isLoggingOut ? 'Signing out...' : 'Sign out'}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
