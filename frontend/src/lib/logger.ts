const isDev = import.meta.env.DEV;

export const logger = {
  error: (...args: unknown[]) => console.error(...args),
  warn: (...args: unknown[]) => { if (isDev) console.warn(...args); },
};
