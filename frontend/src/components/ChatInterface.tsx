'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { Message as MessageType, Source } from '@/types'
import { Message } from './Message'
import { streamChat } from '@/lib/api'

const SESSION_ID = `session-${Date.now()}`

const EXAMPLE_QUESTIONS = [
  'ვარ IT ფრილანსერი მცირე ბიზნესის სტატუსით. წლიური შემოსავალი 50,000 ლარია. რა გადასახადები მეკისრება?',
  'რა არის დღგ-ის რეგისტრაციის ზღვარი ინდივიდუალური მეწარმისთვის?',
  'I am a freelancer with Small Business status. How do I declare foreign income?',
]

export function ChatInterface() {
  const [messages, setMessages] = useState<MessageType[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = useCallback(async (query: string) => {
    if (!query.trim() || isLoading) return

    const userMessage: MessageType = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query.trim(),
      sources: [],
      agentSteps: [],
      lowConfidence: false,
      cached: false,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: MessageType = {
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
      agentSteps: [],
      lowConfidence: false,
      cached: false,
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, assistantMessage])

    const history = messages.map(m => ({ role: m.role, content: m.content }))

    try {
      let accumulatedText = ''
      const steps: string[] = []

      for await (const event of streamChat(query, SESSION_ID, history)) {
        if (event.type === 'status' && event.content) {
          steps.push(event.content)
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, agentSteps: [...steps] } : m
            )
          )
        } else if (event.type === 'token' && event.content) {
          accumulatedText += event.content
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, content: accumulatedText } : m
            )
          )
        } else if (event.type === 'sources') {
          const sources = (event as any).sources as Source[]
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, sources: sources || [] } : m
            )
          )
        } else if (event.type === 'meta') {
          const meta = event as any
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, lowConfidence: meta.low_confidence || false, cached: meta.cached || false }
                : m
            )
          )
        } else if (event.type === 'error' && event.content) {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `Error: ${event.content}` }
                : m
            )
          )
        }
      }
    } catch (err) {
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: 'Connection error. Please try again.' }
            : m
        )
      )
    } finally {
      setIsLoading(false)
      inputRef.current?.focus()
    }
  }, [messages, isLoading])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(input)
    }
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto max-w-3xl">
          <h1 className="text-lg font-semibold text-slate-900">RSHub</h1>
          <p className="text-xs text-slate-500">
            Georgian tax consultation for Individual Entrepreneurs and small businesses
          </p>
        </div>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 && (
            <div className="py-12 text-center">
              <div className="mb-2 text-2xl">📋</div>
              <h2 className="text-base font-medium text-slate-700">
                Ask a tax question
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Answers are based on the Georgian Tax Code and official rs.ge guidance.
              </p>
              <div className="mt-6 space-y-2">
                {EXAMPLE_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => handleSubmit(q)}
                    className="block w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm hover:border-brand-300 hover:bg-brand-50 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <Message
              key={msg.id}
              message={msg}
              isStreaming={isLoading && i === messages.length - 1 && msg.role === 'assistant'}
            />
          ))}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="border-t border-slate-200 bg-white px-4 py-4">
        <div className="mx-auto max-w-3xl">
          <div className="flex items-end gap-3 rounded-2xl border border-slate-300 bg-white px-4 py-3 shadow-sm focus-within:border-brand-500 focus-within:ring-1 focus-within:ring-brand-500">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a tax question in Georgian or English..."
              rows={1}
              disabled={isLoading}
              className="flex-1 resize-none bg-transparent text-sm text-slate-900 placeholder-slate-400 outline-none disabled:opacity-50"
              style={{ maxHeight: '120px' }}
            />
            <button
              onClick={() => handleSubmit(input)}
              disabled={!input.trim() || isLoading}
              className={clsx(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors',
                input.trim() && !isLoading
                  ? 'bg-brand-500 text-white hover:bg-brand-600'
                  : 'bg-slate-100 text-slate-400'
              )}
            >
              {isLoading ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Send size={16} />
              )}
            </button>
          </div>
          <p className="mt-2 text-center text-[10px] text-slate-400">
            Informational only. Not legal advice. Verify cited articles before acting.
          </p>
        </div>
      </div>
    </div>
  )
}
