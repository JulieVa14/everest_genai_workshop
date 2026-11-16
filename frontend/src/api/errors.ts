export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(message: string, status = 0, code = 'unavailable') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'Request failed. Check the local backend and reconnect.';
  return error.message.replace(/sk-[a-zA-Z0-9_-]+/g, '[redacted]')
    .replace(/Bearer\s+\S+/gi, '[redacted]').slice(0, 500);
}