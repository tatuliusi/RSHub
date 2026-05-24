'use client'

import { ChevronDown, ChevronUp, Activity } from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'

interface AgentTraceProps {
  steps: string[]
  isStreaming: boolean
}

export function AgentTrace({ steps, isStreaming }: AgentTraceProps) {
  const [open, setOpen] = useState(false)

  if (steps.length === 0) return null

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 text-sm">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-slate-500 hover:text-slate-700"
      >
        <Activity
          size={14}
          className={clsx('shrink-0', isStreaming && 'animate-pulse text-brand-500')}
        />
        <span className="flex-1 text-left text-xs font-medium">
          {isStreaming ? steps[steps.length - 1] : `How this was answered (${steps.length} steps)`}
        </span>
        {!isStreaming && (open ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
      </button>

      {open && !isStreaming && (
        <div className="border-t border-slate-200 px-3 py-2">
          <ol className="space-y-1">
            {steps.map((step, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-slate-500">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-600">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
