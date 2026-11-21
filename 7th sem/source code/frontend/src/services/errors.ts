import axios from 'axios';

/** Extract FastAPI's `detail` message from a failed request, or fall back. */
export const getErrorDetail = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
  }
  return fallback;
};
