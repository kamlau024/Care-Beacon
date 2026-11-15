import type { ThreadSummary } from "./types"

/**
 * Keeps the last-loaded conversation list for this browser tab so the History panel can show it
 * instantly while a refresh runs in the background. It lives at module level, so it survives the
 * Chat page unmounting (switching to Search and back).
 */
export interface ThreadListStore {
  /** The last list loaded, or null if none has loaded yet. */
  get(): ThreadSummary[] | null
  /** Replace the cached list, e.g. after a rename or delete. */
  set(threads: ThreadSummary[]): void
  /**
   * Fetch a fresh list and cache it. Resolves with the list, or with null if a newer refresh
   * started meanwhile (the newer one wins, so a slow, stale response never overwrites it).
   * Rejects if the fetch fails; the cached list is left as it was.
   */
  refresh(): Promise<ThreadSummary[] | null>
}

export function createThreadListStore(
  fetchList: () => Promise<{ threads: ThreadSummary[] }>
): ThreadListStore {
  let cached: ThreadSummary[] | null = null
  let latest = 0

  return {
    get: () => cached,
    set: (threads) => {
      latest++ // a local edit is newer than any response still in flight
      cached = threads
    },
    async refresh() {
      const id = ++latest
      const { threads } = await fetchList()
      if (id !== latest) return null
      cached = threads
      return threads
    },
  }
}
