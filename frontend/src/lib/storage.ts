/**
 * Safe wrappers around sessionStorage/localStorage.
 * Prevents crashes in private browsing mode or when storage is full.
 */

export function safeGetItem(storage: Storage, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSetItem(storage: Storage, key: string, value: string): void {
  try {
    storage.setItem(key, value);
  } catch {
    // Storage full or blocked (private browsing) — silently ignore
  }
}

export function safeRemoveItem(storage: Storage, key: string): void {
  try {
    storage.removeItem(key);
  } catch {
    // Silently ignore
  }
}
