import { describe, it, expect } from 'vitest';
import { formatBackendStatusLabel } from './status';

describe('formatBackendStatusLabel', () => {
  it('formats connected status correctly', () => {
    expect(formatBackendStatusLabel('connected')).toBe('Backend: Connected');
  });

  it('formats unavailable status correctly', () => {
    expect(formatBackendStatusLabel('unavailable')).toBe('Backend: Unavailable');
  });

  it('formats checking status correctly', () => {
    expect(formatBackendStatusLabel('checking')).toBe('Checking...');
  });
});
