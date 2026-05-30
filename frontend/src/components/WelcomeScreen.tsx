'use client'

import { Scale, BookOpen, Globe, ShieldCheck, Zap, ArrowRight } from 'lucide-react'

const FEATURES = [
  {
    icon: BookOpen,
    title: 'Source-cited answers',
    description: 'Every claim traced to a specific Tax Code article or official rs.ge circular',
    color: 'text-sky-500',
    bg: 'bg-sky-50',
    border: 'border-sky-100',
  },
  {
    icon: Globe,
    title: 'Bilingual support',
    description: 'Ask in Georgian or English — answers match your language automatically',
    color: 'text-emerald-500',
    bg: 'bg-emerald-50',
    border: 'border-emerald-100',
  },
  {
    icon: ShieldCheck,
    title: 'Critic-verified',
    description: 'A dedicated AI critic validates every citation before the answer reaches you',
    color: 'text-violet-500',
    bg: 'bg-violet-50',
    border: 'border-violet-100',
  },
  {
    icon: Zap,
    title: 'Semantic cache',
    description: 'Frequently asked questions answered instantly with no redundant processing',
    color: 'text-amber-500',
    bg: 'bg-amber-50',
    border: 'border-amber-100',
  },
]

const EXAMPLE_QUESTIONS = [
  {
    text: 'ვარ IT ფრილანსერი მცირე ბიზნესის სტატუსით. წლიური შემოსავალი 50,000 ლარია. რა გადასახადები მეკისრება?',
    lang: 'GE',
  },
  {
    text: 'What is the VAT registration threshold for Individual Entrepreneurs in Georgia?',
    lang: 'EN',
  },
  {
    text: 'I am a freelancer with Small Business status. How do I declare foreign income?',
    lang: 'EN',
  },
]

interface WelcomeScreenProps {
  onSelect: (question: string) => void
}

export function WelcomeScreen({ onSelect }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-6 py-12 animate-fade-in">
      {/* Hero section */}
      <div className="mb-10 text-center">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-xl shadow-brand-500/25">
          <Scale size={30} className="text-white" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2 tracking-tight">
          Georgian Tax Assistant
        </h1>
        <p className="text-sm text-slate-500 max-w-md leading-relaxed">
          Ask any question about Georgian tax law. Get cited, verified answers sourced
          directly from the Tax Code and official Revenue Service guidance.
        </p>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-2 gap-3 mb-9 w-full max-w-lg">
        {FEATURES.map((feat) => (
          <div
            key={feat.title}
            className={`rounded-xl border ${feat.border} bg-white p-4 shadow-sm hover:shadow-md transition-shadow`}
          >
            <div className={`mb-3 inline-flex h-8 w-8 items-center justify-center rounded-lg ${feat.bg}`}>
              <feat.icon size={15} className={feat.color} />
            </div>
            <div className="text-xs font-semibold text-slate-800 mb-1">{feat.title}</div>
            <div className="text-[11px] text-slate-500 leading-relaxed">{feat.description}</div>
          </div>
        ))}
      </div>

      {/* Example questions */}
      <div className="w-full max-w-lg">
        <div className="mb-3 text-center text-[10px] font-bold uppercase tracking-[0.12em] text-slate-400">
          Try asking
        </div>
        <div className="space-y-2">
          {EXAMPLE_QUESTIONS.map((q, i) => (
            <button
              key={i}
              onClick={() => onSelect(q.text)}
              className="group flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition-all hover:border-brand-300 hover:bg-brand-50 hover:shadow-md active:scale-[0.99]"
            >
              <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-500 transition-colors group-hover:bg-brand-100 group-hover:text-brand-600">
                {q.lang}
              </span>
              <span className="flex-1 text-xs text-slate-700 leading-relaxed transition-colors group-hover:text-slate-900">
                {q.text}
              </span>
              <ArrowRight
                size={13}
                className="shrink-0 text-slate-300 transition-all group-hover:translate-x-0.5 group-hover:text-brand-400"
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
