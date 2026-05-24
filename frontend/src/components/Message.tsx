'use client'

import clsx from 'clsx'
import { User, Bot, Zap } from 'lucide-react'
import { Message as MessageType } from '@/types'
import { AgentTrace } from './AgentTrace'
import { SourcePanel } from './SourcePanel'

interface MessageProps {
  message: MessageType
  isStreaming?: boolean
}

export function Message({ message, isStreaming = false }: MessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={clsx('flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div
        className={clsx(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white',
          isUser ? 'bg-brand-500' : 'bg-slate-700'
        )}
      >
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      {/* Bubble */}
      <div className={clsx('max-w-2xl', isUser ? 'items-end' : 'items-start')}>
        <div
          className={clsx(
            'rounded-2xl px-4 py-3 text-sm leading-relaxed',
            isUser
              ? 'rounded-tr-sm bg-brand-500 text-white'
              : 'rounded-tl-sm bg-white shadow-sm border border-slate-200 text-slate-800'
          )}
        >
          {/* Cached badge */}
          {!isUser && message.cached && (
            <div className="mb-1.5 flex items-center gap-1 text-[10px] font-medium text-slate-400">
              <Zap size={10} />
              cached response
            </div>
          )}

          {/* Message text with streaming cursor */}
          <div
            className={clsx(
              'whitespace-pre-wrap',
              isStreaming && !isUser && 'cursor-blink'
            )}
          >
            {message.content || (isStreaming ? '' : '')}
          </div>
        </div>

        {/* Agent trace (assistant only) */}
        {!isUser && (
          <AgentTrace steps={message.agentSteps} isStreaming={isStreaming} />
        )}

        {/* Sources (assistant only, after streaming) */}
        {!isUser && !isStreaming && message.sources.length > 0 && (
          <SourcePanel sources={message.sources} lowConfidence={message.lowConfidence} />
        )}

        {/* Timestamp */}
        <div className={clsx('mt-1 text-[10px] text-slate-400', isUser ? 'text-right' : 'text-left')}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}
