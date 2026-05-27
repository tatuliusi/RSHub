import { StreamEvent } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 3-minute timeout; the pipeline can take up to ~30s on first iteration, longer with retries
const STREAM_TIMEOUT_MS = 180_000

export async function* streamChat(
  query: string,
  sessionId: string,
  history: { role: string; content: string }[]
): AsyncGenerator<StreamEvent> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS)

  let response: Response
  try {
    response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query,
        session_id: sessionId,
        conversation_history: history,
      }),
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timeoutId)
    throw err
  }

  if (!response.ok) {
    clearTimeout(timeoutId)
    throw new Error(`API error: ${response.status}`)
  }

  const body = response.body
  if (!body) {
    clearTimeout(timeoutId)
    throw new Error('Response body is not readable')
  }

  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const event: StreamEvent = JSON.parse(raw)
            yield event
          } catch {
            // skip malformed SSE lines
          }
        }
      }
    }
  } finally {
    clearTimeout(timeoutId)
    reader.releaseLock()
  }
}
