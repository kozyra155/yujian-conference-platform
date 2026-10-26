/** Indico returns HTTP validation errors as {error: {message: ...}}. */
export function errorMessage(data, fallback) {
 for (const value of [data?.message, data?.error?.message, data?.error, data?.description]) {
  if (typeof value === 'string' && value.trim()) return value.trim();
 }
 return fallback;
}
