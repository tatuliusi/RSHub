'use client'

import { ExternalLink, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import { Source } from '@/types'

interface SourcePanelProps {
  sources: Source[]
  lowConfidence: boolean
}

const SOURCE_LABELS: Record<string, string> = {
  tax_code: 'Tax Code',
  circular: 'Circular',
  form: 'Form',
  guidance: 'Guidance',
}

export function SourcePanel({ sources, lowConfidence }: SourcePanelProps) {
  const [open, setOpen] = useState(false)

  if (sources.length === 0) return null

  return (
    <div className="mt-3">
      {lowConfidence && (
        <div className="mb-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-700 border border-amber-200">
          This answer could not be fully verified. Please check the cited sources directly.
        </div>
      )}

      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium text-brand-600 hover:text-brand-700"
      >
        <BookOpen size={13} />
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((source, i) => (
            <div
              key={i}
              className="flex items-start justify-between gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <span className="inline-block rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-700 mr-1.5">
                  {SOURCE_LABELS[source.source_type] || source.source_type}
                  {source.article_number ? ` ${source.article_number}` : ''}
                </span>
                <span className="text-slate-700">{source.title}</span>
                <div className="mt-0.5 text-slate-400">
                  Last updated: {source.last_modified}
                </div>
              </div>
              {source.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-slate-400 hover:text-brand-500"
                >
                  <ExternalLink size={13} />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
