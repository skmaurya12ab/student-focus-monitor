import { BackendStatus } from '../types/api';

/**
 * Returns a human-readable display label for a given backend status.
 */
export function formatBackendStatusLabel(status: BackendStatus): string {
  switch (status) {
    case 'connected':
      return 'Backend: Connected';
    case 'unavailable':
      return 'Backend: Unavailable';
    case 'checking':
    default:
      return 'Checking...';
  }
}
