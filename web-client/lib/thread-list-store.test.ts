import { describe, expect, it } from "vitest"
import { createThreadListStore } from "./thread-list-store"
import type { ThreadSummary } from "./types"

const thread = (id: string): ThreadSummary =>
  ({ id, title: id, last_activity_at: "2026-11-14T00:00:00Z", message_count: 2 }) as ThreadSummary

function deferred<T>() {
  let resolve!: (v: T) => void
  let reject!: (e: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe("thread list store", () => {
  it("starts empty and caches a successful refresh", async () => {
    const store = createThreadListStore(async () => ({ threads: [thread("a")] }))
    expect(store.get()).toBeNull()
    expect(await store.refresh()).toEqual([thread("a")])
    expect(store.get()).toEqual([thread("a")])
  })

  it("lets the newest refresh win when responses arrive out of order", async () => {
    const calls = [deferred<{ threads: ThreadSummary[] }>(), deferred<{ threads: ThreadSummary[] }>()]
    let n = 0
    const store = createThreadListStore(() => calls[n++].promise)
    const first = store.refresh()
    const second = store.refresh()
    calls[1].resolve({ threads: [thread("new")] })
    calls[0].resolve({ threads: [thread("old")] })
    expect(await second).toEqual([thread("new")])
    expect(await first).toBeNull()
    expect(store.get()).toEqual([thread("new")])
  })

  it("keeps the cached list when a refresh fails", async () => {
    let fail = false
    const store = createThreadListStore(async () => {
      if (fail) throw new Error("down")
      return { threads: [thread("a")] }
    })
    await store.refresh()
    fail = true
    await expect(store.refresh()).rejects.toThrow("down")
    expect(store.get()).toEqual([thread("a")])
  })

  it("does not let an in-flight response overwrite a local edit", async () => {
    const call = deferred<{ threads: ThreadSummary[] }>()
    const store = createThreadListStore(() => call.promise)
    const pending = store.refresh()
    store.set([]) // e.g. the user deleted the only thread
    call.resolve({ threads: [thread("deleted")] })
    expect(await pending).toBeNull()
    expect(store.get()).toEqual([])
  })
})
