export interface SSEEvent {
  event: string
  data: unknown
}

/**
 * Parse as many complete SSE frames as `buffer` holds. Returns the parsed
 * events plus the unconsumed remainder, to be prepended to the next chunk.
 */
export function parseSSE(buffer: string): { events: SSEEvent[]; rest: string } {
  const events: SSEEvent[] = []
  // Normalise CRLF; a lone trailing "\r" may be half of a split CRLF, so keep it in rest.
  let text = buffer.replace(/\r\n/g, "\n")
  let tail = ""
  if (text.endsWith("\r")) {
    tail = "\r"
    text = text.slice(0, -1)
  }
  text = text.replace(/\r/g, "\n")

  const frames = text.split("\n\n")
  const rest = frames.pop() ?? ""

  for (const frame of frames) {
    let event = "message"
    const data: string[] = []
    for (const line of frame.split("\n")) {
      if (!line || line.startsWith(":")) continue
      const idx = line.indexOf(":")
      const field = idx === -1 ? line : line.slice(0, idx)
      let value = idx === -1 ? "" : line.slice(idx + 1)
      if (value.startsWith(" ")) value = value.slice(1)
      if (field === "event") event = value
      else if (field === "data") data.push(value)
    }
    if (!data.length) continue
    try {
      events.push({ event, data: JSON.parse(data.join("\n")) })
    } catch {
      // Malformed payload: skip the frame rather than kill the stream.
    }
  }
  return { events, rest: rest + tail }
}
