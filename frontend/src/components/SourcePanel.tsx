'use client'

import { useState } from 'react'
import { ExternalLink, BookOpen, ChevronDown, ChevronUp, FileText, FileCheck, ClipboardList, Lightbulb } from 'lucide-react'
import { Source } from '@/types'

interface SourcePanelProps {
  sources: Source[]
  lowConfidence?: boolean
}

type SourceConfig = {
  label: string
  Icon: React.ElementType
  color: string
  bg: string
  border: string
  badge: string
}

const SOURCE_CONFIG: Record<string, SourceConfig> = {
  tax_code: {
    label: 'Tax Code',
    Icon: FileText,
    color: 'text-brand-600',
    bg: 'bg-brand-50',
    border: 'border-brand-100',
    badge: 'bg-brand-100 text-brand-700',
  },
  circular: {
    label: 'Circular',
    Icon: FileCheck,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50',
    border: 'border-emerald-100',
    badge: 'bg-emerald-100 text-emerald-700',
  },
  form: {
    label: 'Form',
    Icon: ClipboardList,
    color: 'text-violet-600',
    bg: 'bg-violet-50',
    border: 'border-violet-100',
    badge: 'bg-violet-100 text-violet-700',
  },
  guidance: {
    label: 'Guidance',
    Icon: Lightbulb,
    color: 'text-amber-600',
    bg: 'bg-amber-50',
    border: 'border-amber-100',
    badge: 'bg-amber-100 text-amber-700',
  },
}

const DEFAULT_CONFIG: SourceConfig = {
  label: 'Source',
  Icon: BookOpen,
  color: 'text-slate-600',
  bg: 'bg-slate-50',
  border: 'border-slate-200',
  badge: 'bg-slate-100 text-slate-600',
}

export function SourcePanel({ sources, lowConfidence }: SourcePanelProps) {
  const [open, setOpen] = useState(false)

  if (sources.length === 0) return null

  return (
    <div className="mt-2.5 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Toggle header */}
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-slate-50"
      >
        <BookOpen size={13} className="shrink-0 text-slate-400" />
        <span className="flex-1 text-xs font-medium text-slate-600">
          Sources cited
          <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-normal text-slate-500">
            {sources.length}
          </span>
        </span>
        {open ? (
          <ChevronUp size={13} className="text-slate-400" />
        ) : (
          <ChevronDown size={13} className="text-slate-400" />
        )}
      </button>

      {open && (
        <div className="border-t border-slate-100 px-3 pb-3 pt-2">
          <div className="space-y-2">
            {sources.map((source, i) => {
              const cfg = SOURCE_CONFIG[source.source_type] ?? DEFAULT_CONFIG
              const { Icon } = cfg
              return (
                <div
                  key={i}
                  className={`flex items-start gap-3 rounded-lg border ${cfg.border} ${cfg.bg} px-3 py-2.5 transition-colors hover:brightness-95`}
                >
                  {/* Icon */}
                  <div className="mt-0.5 shrink-0">
                    <Icon size={14} className={cfg.color} />
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
                      <span className={`inline-block rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${cfg.badge}`}>
                        {cfg.label}
                      </span>
                      {source.article_number && (
                        <span className="text-[10px] font-semibold text-slate-600">
                          Art. {source.article_number}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-700 leading-snug">{source.title}</div>
                    {source.last_modified && (
                      <div className="mt-0.5 text-[10px] text-slate-400">
                        Updated {source.last_modified}
                      </div>
                    )}
                  </div>

                  {/* External link */}
                  {source.url && (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`mt-0.5 shrink-0 transition-colors ${cfg.color} opacity-60 hover:opacity-100`}
                      title="Open source"
                    >
                      <ExternalLink size={13} />
                    </a>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
