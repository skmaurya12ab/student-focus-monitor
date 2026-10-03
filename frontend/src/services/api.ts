import { HealthResponse } from '../types/api';

/**
 * Base URL for backend API requests, configured via VITE_API_BASE_URL.
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Checks the availability of the backend service via GET /api/health.
 * Returns true if the backend returns HTTP 200 with status: "ok", otherwise false.
 */
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      return false;
    }

    const data: HealthResponse = await response.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}
