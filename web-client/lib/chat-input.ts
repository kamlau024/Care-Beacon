// Mirrors MIN_MESSAGE_LENGTH / MAX_MESSAGE_LENGTH in api/src/api/chat_models.py.
export const MIN_MESSAGE_LENGTH = 3
export const MAX_MESSAGE_LENGTH = 500
const COUNTER_FROM = 400

/** True when there is text, but too little for the server to accept. */
export function tooShort(text: string): boolean {
  const n = text.trim().length
  return n > 0 && n < MIN_MESSAGE_LENGTH
}

/** Show the character counter once the input nears the limit. */
export function showCounter(length: number): boolean {
  return length >= COUNTER_FROM
}

/** Put the typed text back when the server rejected the request (4xx). */
export function restoreInputAfter(httpStatus: number | undefined): boolean {
  return httpStatus !== undefined && httpStatus >= 400 && httpStatus < 500
}

/**
 * Whether to move focus to the question box automatically. Not on touch-first devices: focusing a
 * text field there opens the on-screen keyboard, which would cover the answer just shown.
 */
export function autoFocusAllowed(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return true
  return !window.matchMedia("(pointer: coarse)").matches
}
