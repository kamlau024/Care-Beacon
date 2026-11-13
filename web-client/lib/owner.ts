const STORAGE_KEY = "care-beacon-owner-key"

// Used when localStorage is unavailable (private mode, blocked storage).
let memoryKey: string | null = null

export function getOwnerKey(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing) return existing
    const created = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEY, created)
    return created
  } catch {
    if (!memoryKey) memoryKey = crypto.randomUUID()
    return memoryKey
  }
}
