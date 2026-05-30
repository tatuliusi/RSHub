'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Menu, Scale, Plus } from 'lucide-react'
import clsx from 'clsx'
import { Message as MessageType, Source, ConversationSession } from '@/types'
import { Message } from './Message'
import { Sidebar } from './Sidebar'
import { WelcomeScreen } from './WelcomeScreen'
import { streamChat } from '@/lib/api'

const MAX_HISTORY_TURNS = 8
const SESSION_ID_KEY = 'rshub_session_id'
const SESSIONS_KEY = 'rshub_sessions'
const MAX_SESSIONS = 15

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function getOrCreateSessionId(): string {
  try {
    const stored = localStorage.getItem(SESSION_ID_KEY)
    if (stored) return stored
    const id = generateSessionId()
    localStorage.setItem(SESSION_ID_KEY, id)
    return id
  } catch {
    return generateSessionId()
  }
}

function loadSessions(): ConversationSession[] {
  try {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]')
  } catch {
    return []
  }
}

function saveSessions(sessions: ConversationSession[]) {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(0, MAX_SESSIONS)))
  } catch {}
}

export function ChatInterface() {
  const [messages, setMessages] = useState<MessageType[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState('')
  const [sessions, setSessions] = useState<ConversationSession[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const id = getOrCreateSessionId()
    setSessionId(id)
    setSessions(loadSessions())
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 128) + 'px'
  }, [input])

  const handleNewChat = useCallback(() => {
    const newId = generateSessionId()
    try {
      localStorage.setItem(SESSION_ID_KEY, newId)
    } catch {}
    setSessionId(newId)
    setMessages([])
    setInput('')
    setSidebarOpen(false)
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  const registerSession = useCallback(
    (firstMessage: string, currentId: string) => {
      setSessions((prev) => {
        const existing = prev.find((s) => s.id === currentId)
        let updated: ConversationSession[]
        if (existing) {
          updated = prev.map((s) =>
            s.id === currentId ? { ...s, messageCount: s.messageCount + 2 } : s
          )
        } else {
          const title =
            firstMessage.length > 52 ? firstMessage.slice(0, 52) + '…' : firstMessage
          updated = [{ id: currentId, title, timestamp: Date.now(), messageCount: 2 }, ...prev]
        }
        saveSessions(updated)
        return updated
      })
    },
    []
  )

  const handleSubmit = useCallback(
    async (query: string) => {
      if (!query.trim() || isLoading) return
      const trimmed = query.trim()
      const isFirstMessage = messages.length === 0

      const userMsg: MessageType = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmed,
        sources: [],
        agentSteps: [],
        lowConfidence: false,
        cached: false,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, userMsg])
      setInput('')
      setIsLoading(true)

      if (isFirstMessage) registerSession(trimmed, sessionId)

      const assistantId = `assistant-${Date.now()}`
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          sources: [],
          agentSteps: [],
          lowConfidence: false,
          cached: false,
          timestamp: new Date(),
        },
      ])

      const history = [...messages, userMsg]
        .slice(-MAX_HISTORY_TURNS)
        .map((m) => ({ role: m.role, content: m.content }))

      try {
        let accumulated = ''
        const steps: string[] = []

        for await (const event of streamChat(trimmed, sessionId, history)) {
          if (event.type === 'status' && event.content) {
            steps.push(event.content)
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, agentSteps: [...steps] } : m))
            )
          } else if (event.type === 'token' && event.content) {
            accumulated += event.content
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, content: accumulated } : m))
            )
          } else if (event.type === 'sources') {
            const sources = (event as any).sources as Source[]
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, sources: sources || [] } : m))
            )
          } else if (event.type === 'meta') {
            const meta = event as any
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, lowConfidence: meta.low_confidence || false, cached: meta.cached || false }
                  : m
              )
            )
          } else if (event.type === 'error' && event.content) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: `⚠️ ${event.content}` } : m
              )
            )
          }
        }
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: '⚠️ Connection error. Please check your connection and try again.' }
              : m
          )
        )
      } finally {
        setIsLoading(false)
        inputRef.current?.focus()
      }
    },
    [messages, isLoading, sessionId, registerSession]
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(input)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={clsx(
          'fixed inset-y-0 left-0 z-30 transition-transform duration-300 md:relative md:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <Sidebar sessionId={sessionId} sessions={sessions} onNewChat={handleNewChat} />
      </div>

      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 shadow-sm">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 md:hidden"
          >
            <Menu size={18} />
          </button>

          <div className="flex items-center gap-2.5 min-w-0">
            <div className="hidden md:flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 shadow-sm shadow-brand-500/20">
              <Scale size={14} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-slate-900">RSHub</span>
            <span className="hidden sm:block text-xs text-slate-400">·</span>
            <span className="hidden sm:block text-xs text-slate-400">Georgian Tax Assistant</span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            {isLoading && (
              <span className="flex items-center gap-1.5 text-xs text-brand-500">
                <Loader2 size={12} className="animate-spin" />
                <span className="hidden sm:inline">Processing…</span>
              </span>
            )}
            {messages.length > 0 && (
              <button
                onClick={handleNewChat}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition-colors hover:bg-slate-50 hover:border-slate-300"
              >
                <Plus size={12} />
                <span>New chat</span>
              </button>
            )}
          </div>
        </header>

        {/* Messages / Welcome */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onSelect={handleSubmit} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
              {messages.map((msg, i) => (
                <Message
                  key={msg.id}
                  message={msg}
                  isStreaming={
                    isLoading && i === messages.length - 1 && msg.role === 'assistant'
                  }
                />
              ))}
              <div ref={bottomRef} className="h-4" />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-slate-200 bg-white px-4 py-3.5">
          <div className="mx-auto max-w-3xl">
            <div className="relative flex items-end rounded-2xl border border-slate-300 bg-white shadow-sm transition-all focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-500/15">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a tax question in Georgian or English…"
                rows={1}
                disabled={isLoading}
                className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-slate-900 placeholder-slate-400 outline-none disabled:opacity-50"
                style={{ maxHeight: '128px' }}
              />
              <div className="flex items-center pb-2.5 pr-3">
                <button
                  onClick={() => handleSubmit(input)}
                  disabled={!input.trim() || isLoading}
                  className={clsx(
                    'flex h-8 w-8 items-center justify-center rounded-xl transition-all',
                    input.trim() && !isLoading
                      ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/30 hover:bg-brand-600 active:scale-95'
                      : 'cursor-not-allowed bg-slate-100 text-slate-400'
                  )}
                >
                  {isLoading ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <Send size={15} />
                  )}
                </button>
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between px-1">
              <p className="text-[10px] text-slate-400">
                Informational only · Not legal advice · Verify cited articles before acting
              </p>
              <p className="hidden sm:block text-[10px] text-slate-400">
                ⏎ Send · ⇧⏎ New line
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
