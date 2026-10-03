/**
 * Backend health check response schema.
 */
export interface HealthResponse {
  status: string;
}

/**
 * Frontend representation of the backend connectivity status.
 */
export type BackendStatus = 'checking' | 'connected' | 'unavailable';
