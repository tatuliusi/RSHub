'use client'

import { useState } from 'react'
import clsx from 'clsx'
import { User, Scale, Zap, Copy, Check, AlertCircle } from 'lucide-react'
import { Message as MessageType } from '@/types'
import { AgentTrace } from './AgentTrace'
import { SourcePanel } from './SourcePanel'

interface MessageProps {
  message: MessageType
  isStreaming?: boolean
}

// — Inline markdown: **bold**, *italic*, `code`
function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g)
  if (parts.length === 1) return text
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
          return (
            <strong key={i} className="font-semibold text-slate-900">
              {part.slice(2, -2)}
            </strong>
          )
        }
        if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
          return <em key={i}>{part.slice(1, -1)}</em>
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return (
            <code
              key={i}
              className="rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700"
            >
              {part.slice(1, -1)}
            </code>
          )
        }
        return part || null
      })}
    </>
  )
}

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'hr' }
  | { type: 'empty' }
  | { type: 'paragraph'; text: string }

function parseBlocks(text: string): Block[] {
  const lines = text.split('\n')
  const blocks: Block[] = []

  for (const line of lines) {
    const last = blocks[blocks.length - 1]

    if (/^---+$/.test(line.trim())) {
      blocks.push({ type: 'hr' })
    } else if (line.startsWith('### ')) {
      blocks.push({ type: 'h3', text: line.slice(4) })
    } else if (line.startsWith('## ')) {
      blocks.push({ type: 'h2', text: line.slice(3) })
    } else if (line.startsWith('# ')) {
      blocks.push({ type: 'h1', text: line.slice(2) })
    } else if (/^[-*•] /.test(line)) {
      const item = line.replace(/^[-*•] /, '')
      if (last?.type === 'ul') {
        last.items.push(item)
      } else {
        blocks.push({ type: 'ul', items: [item] })
      }
    } else if (/^\d+\. /.test(line)) {
      const item = line.replace(/^\d+\. /, '')
      if (last?.type === 'ol') {
        last.items.push(item)
      } else {
        blocks.push({ type: 'ol', items: [item] })
      }
    } else if (line.trim() === '') {
      blocks.push({ type: 'empty' })
    } else {
      blocks.push({ type: 'paragraph', text: line })
    }
  }

  return blocks
}

function MarkdownContent({ text }: { text: string }) {
  const blocks = parseBlocks(text)

  return (
    <div className="space-y-1">
      {blocks.map((block, i) => {
        if (block.type === 'hr') {
          return <hr key={i} className="my-2 border-slate-200" />
        }
        if (block.type === 'empty') {
          return <div key={i} className="h-1.5" />
        }
        if (block.type === 'h1') {
          return (
            <h2 key={i} className="mt-3 mb-1 text-base font-bold text-slate-900">
              {renderInline(block.text)}
            </h2>
          )
        }
        if (block.type === 'h2') {
          return (
            <h3 key={i} className="mt-3 mb-1 text-sm font-bold text-slate-800 border-b border-slate-100 pb-1">
              {renderInline(block.text)}
            </h3>
          )
        }
        if (block.type === 'h3') {
          return (
            <h4 key={i} className="mt-2 mb-0.5 text-sm font-semibold text-slate-800">
              {renderInline(block.text)}
            </h4>
          )
        }
        if (block.type === 'ul') {
          return (
            <ul key={i} className="my-2 space-y-1.5">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2.5">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" />
                  <span className="leading-relaxed text-slate-700">{renderInline(item)}</span>
                </li>
              ))}
            </ul>
          )
        }
        if (block.type === 'ol') {
          return (
            <ol key={i} className="my-2 space-y-1.5">
              {block.items.map((item, j) => (
                <li key={j} className="flex items-start gap-2.5">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-bold text-brand-600">
                    {j + 1}
                  </span>
                  <span className="leading-relaxed text-slate-700">{renderInline(item)}</span>
                </li>
              ))}
            </ol>
          )
        }
        return (
          <p key={i} className="leading-relaxed text-slate-700">
            {renderInline(block.text)}
          </p>
        )
      })}
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {}
  }

  return (
    <button
      onClick={handleCopy}
      title="Copy message"
      className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
    >
      {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
    </button>
  )
}

export function Message({ message, isStreaming = false }: MessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={clsx('message-in flex gap-3', isUser ? 'flex-row-reverse' : 'flex-row')}>
      {/* Avatar */}
      <div
        className={clsx(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full shadow-sm',
          isUser
            ? 'bg-gradient-to-br from-brand-400 to-brand-600 text-white'
            : 'bg-gradient-to-br from-slate-700 to-slate-800 text-white'
        )}
      >
        {isUser ? <User size={14} /> : <Scale size={14} />}
      </div>

      {/* Content column */}
      <div className={clsx('flex min-w-0 max-w-[84%] flex-col', isUser ? 'items-end' : 'items-start')}>
        {/* Bubble */}
        <div
          className={clsx(
            'rounded-2xl px-4 py-3 text-sm',
            isUser
              ? 'rounded-tr-sm bg-gradient-to-br from-brand-500 to-brand-600 text-white shadow-sm shadow-brand-500/20'
              : 'rounded-tl-sm border border-slate-200 bg-white text-slate-800 shadow-sm'
          )}
        >
          {/* Cached badge */}
          {!isUser && message.cached && (
            <div className="mb-2 flex items-center gap-1 text-[10px] font-medium text-slate-400">
              <Zap size={10} className="text-amber-400" />
              Cached response
            </div>
          )}

          {isUser ? (
            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
          ) : message.content ? (
            <div className={clsx(isStreaming && 'cursor-blink')}>
              <MarkdownContent text={message.content} />
            </div>
          ) : isStreaming ? (
            <div className="flex items-center gap-1 py-1 dot-bounce">
              <span className="inline-block h-2 w-2 rounded-full bg-slate-300" />
              <span className="inline-block h-2 w-2 rounded-full bg-slate-300" />
              <span className="inline-block h-2 w-2 rounded-full bg-slate-300" />
            </div>
          ) : null}
        </div>

        {/* Controls row (assistant only) */}
        {!isUser && message.content && !isStreaming && (
          <div className="mt-1 flex items-center gap-1 px-1">
            <CopyButton text={message.content} />
          </div>
        )}

        {/* Agent trace */}
        {!isUser && (
          <AgentTrace steps={message.agentSteps} isStreaming={isStreaming} />
        )}

        {/* Low confidence warning */}
        {!isUser && !isStreaming && message.lowConfidence && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-700">
            <AlertCircle size={13} className="mt-0.5 shrink-0 text-amber-500" />
            <span>
              This answer could not be fully verified. Please review the cited sources directly.
            </span>
          </div>
        )}

        {/* Sources */}
        {!isUser && !isStreaming && message.sources.length > 0 && (
          <SourcePanel sources={message.sources} lowConfidence={message.lowConfidence} />
        )}

        {/* Timestamp */}
        <div className={clsx('mt-1.5 text-[10px] text-slate-400', isUser ? 'text-right' : 'text-left')}>
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  )
}
