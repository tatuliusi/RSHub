export interface Source {
  article_number: string
  title: string
  url: string
  source_type: string
  last_modified: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  agentSteps: string[]
  lowConfidence: boolean
  cached: boolean
  timestamp: Date
}

export type StreamEventType = 'status' | 'token' | 'sources' | 'meta' | 'done' | 'error'

export interface StreamEvent {
  type: StreamEventType
  content?: string
  sources?: Source[]
  low_confidence?: boolean
  cached?: boolean
}
