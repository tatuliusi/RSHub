'use client'

import { useState } from 'react'
import { ChevronDown, ChevronUp, GitBranch, Search, Sparkles, ShieldCheck, Zap, Activity } from 'lucide-react'
import clsx from 'clsx'

interface AgentTraceProps {
  steps: string[]
  isStreaming: boolean
}

type StepInfo = {
  Icon: React.ElementType
  label: string
  color: string
  bg: string
}

function getStepInfo(step: string): StepInfo {
  const s = step.toLowerCase()
  if (s.includes('plan') || s.includes('decomp') || s.includes('analyz')) {
    return { Icon: GitBranch, label: 'Planner', color: 'text-violet-500', bg: 'bg-violet-50 border-violet-100' }
  }
  if (s.includes('cache')) {
    return { Icon: Zap, label: 'Cache', color: 'text-amber-500', bg: 'bg-amber-50 border-amber-100' }
  }
  if (s.includes('retriev') || s.includes('search') || s.includes('fetch') || s.includes('rerank')) {
    return { Icon: Search, label: 'Retrieval', color: 'text-sky-500', bg: 'bg-sky-50 border-sky-100' }
  }
  if (s.includes('synth') || s.includes('generat') || s.includes('writ') || s.includes('answer')) {
    return { Icon: Sparkles, label: 'Synthesis', color: 'text-emerald-500', bg: 'bg-emerald-50 border-emerald-100' }
  }
  if (s.includes('critic') || s.includes('verif') || s.includes('check') || s.includes('approv')) {
    return { Icon: ShieldCheck, label: 'Critic', color: 'text-brand-500', bg: 'bg-brand-50 border-brand-100' }
  }
  return { Icon: Activity, label: 'Processing', color: 'text-slate-400', bg: 'bg-slate-50 border-slate-100' }
}

function LiveStep({ step }: { step: string }) {
  const { Icon, label, color } = getStepInfo(step)
  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5">
      <div className="relative flex h-6 w-6 shrink-0 items-center justify-center">
        <span className={clsx('absolute inset-0 rounded-full opacity-30 animate-ping', color.replace('text-', 'bg-'))} />
        <Icon size={13} className={clsx(color, 'relative z-10')} />
      </div>
      <span className="flex-1 text-xs text-slate-600 truncate">{step}</span>
      <div className="flex gap-0.5 dot-bounce shrink-0">
        <span className="inline-block h-1 w-1 rounded-full bg-slate-400" />
        <span className="inline-block h-1 w-1 rounded-full bg-slate-400" />
        <span className="inline-block h-1 w-1 rounded-full bg-slate-400" />
      </div>
    </div>
  )
}

export function AgentTrace({ steps, isStreaming }: AgentTraceProps) {
  const [open, setOpen] = useState(false)

  if (steps.length === 0) return null

  return (
    <div className="mt-2.5 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Header / toggle */}
      {isStreaming ? (
        <LiveStep step={steps[steps.length - 1]} />
      ) : (
        <>
          <button
            onClick={() => setOpen(!open)}
            className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-slate-50"
          >
            <Activity size={13} className="shrink-0 text-slate-400" />
            <span className="flex-1 text-xs font-medium text-slate-600">
              How this was answered
              <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-normal text-slate-500">
                {steps.length} steps
              </span>
            </span>
            {open ? (
              <ChevronUp size={13} className="text-slate-400" />
            ) : (
              <ChevronDown size={13} className="text-slate-400" />
            )}
          </button>

          {open && (
            <div className="border-t border-slate-100 px-3 py-3">
              <div className="space-y-2">
                {steps.map((step, i) => {
                  const { Icon, label, color, bg } = getStepInfo(step)
                  const isLast = i === steps.length - 1
                  return (
                    <div key={i} className="step-in flex items-start gap-3" style={{ animationDelay: `${i * 40}ms` }}>
                      {/* Timeline line + dot */}
                      <div className="relative flex flex-col items-center">
                        <div className={clsx('flex h-6 w-6 shrink-0 items-center justify-center rounded-full border', bg)}>
                          <Icon size={11} className={color} />
                        </div>
                        {!isLast && (
                          <div className="mt-1 w-px flex-1 bg-slate-100" style={{ minHeight: '12px' }} />
                        )}
                      </div>
                      {/* Step content */}
                      <div className="flex-1 pb-1 pt-0.5">
                        <div className={clsx('mb-0.5 text-[9px] font-bold uppercase tracking-widest', color)}>
                          {label}
                        </div>
                        <div className="text-[11px] text-slate-600 leading-relaxed">{step}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
