'use client'

import { useEffect } from 'react'
import { Scale, Plus, MessageSquare } from 'lucide-react'
import clsx from 'clsx'
import { ConversationSession } from '@/types'

interface SidebarProps {
  sessionId: string
  sessions: ConversationSession[]
  onNewChat: () => void
}

function timeAgo(ts: number): string {
  const diff = Date.now() - ts
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function Sidebar({ sessionId, sessions, onNewChat }: SidebarProps) {

  return (
    <aside className="flex h-screen w-64 flex-col bg-slate-950 text-slate-400 border-r border-slate-800/60">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-800/60">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-lg shadow-brand-500/20">
          <Scale size={17} className="text-white" />
        </div>
        <div>
          <div className="text-sm font-semibold text-white tracking-wide">RSHub</div>
          <div className="text-[10px] text-slate-500 mt-0.5">Tax Assistant</div>
        </div>
      </div>

      {/* New Chat */}
      <div className="px-3 pt-4">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2.5 rounded-xl border border-brand-500/20 bg-brand-500/10 px-3.5 py-2.5 text-sm font-medium text-brand-400 transition-all hover:border-brand-500/40 hover:bg-brand-500/20 hover:text-brand-300 active:scale-[0.98]"
        >
          <Plus size={15} />
          New Conversation
        </button>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-3 pt-5 pb-2">
        {sessions.length > 0 ? (
          <>
            <div className="mb-2.5 px-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-600">
              Recent
            </div>
            <div className="space-y-0.5">
              {sessions.slice(0, 12).map((session) => (
                <div
                  key={session.id}
                  className={clsx(
                    'group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors',
                    session.id === sessionId
                      ? 'bg-slate-800 text-slate-200'
                      : 'text-slate-500 hover:bg-slate-800/50 hover:text-slate-300'
                  )}
                >
                  <MessageSquare
                    size={12}
                    className={clsx(
                      'shrink-0 transition-colors',
                      session.id === sessionId ? 'text-brand-400' : 'text-slate-600 group-hover:text-slate-400'
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs truncate">{session.title}</div>
                  </div>
                  <div className="shrink-0 text-[9px] text-slate-700 group-hover:text-slate-600">
                    {timeAgo(session.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="px-2 py-4 text-center">
            <MessageSquare size={20} className="mx-auto mb-2 text-slate-700" />
            <p className="text-[10px] text-slate-600">No conversations yet</p>
          </div>
        )}
      </div>

    </aside>
  )
}
