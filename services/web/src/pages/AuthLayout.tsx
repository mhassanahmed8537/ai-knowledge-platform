import { motion } from 'framer-motion'
import { FileText, MessagesSquare, ShieldCheck, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

const FEATURES = [
  { icon: FileText, text: 'Upload private documents and index them automatically' },
  { icon: MessagesSquare, text: 'Ask questions, get streamed answers with inline citations' },
  { icon: ShieldCheck, text: 'Strict tenant isolation with row-level security' },
]

export function AuthLayout({ children, title, subtitle }: { children: ReactNode; title: string; subtitle: string }) {
  return (
    <div className="flex min-h-screen bg-bg">
      <div className="relative hidden w-[45%] flex-col justify-between overflow-hidden bg-brand-950 p-12 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              'radial-gradient(60% 50% at 20% 10%, rgba(139,116,255,0.5), transparent), radial-gradient(50% 40% at 90% 90%, rgba(95,60,224,0.45), transparent)',
          }}
        />
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="relative flex items-center gap-2.5"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="text-sm font-semibold tracking-wide">Knowledge Platform</span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="relative"
        >
          <h1 className="max-w-md text-[2.15rem] font-semibold leading-tight tracking-tight">
            Answers grounded in your organization's own knowledge.
          </h1>
          <div className="mt-10 flex flex-col gap-4">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.text}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: 0.2 + i * 0.08 }}
                className="flex items-center gap-3 text-[15px] text-white/80"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <f.icon className="h-4 w-4" />
                </div>
                {f.text}
              </motion.div>
            ))}
          </div>
        </motion.div>

        <p className="relative text-xs text-white/40">© {new Date().getFullYear()} Knowledge Platform</p>
      </div>

      <div className="flex flex-1 items-center justify-center p-6 sm:p-10">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="w-full max-w-sm"
        >
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
                <Sparkles className="h-4 w-4" />
              </div>
              <span className="text-sm font-semibold text-text">Knowledge Platform</span>
            </div>
          </div>
          <h2 className="text-2xl font-semibold text-text">{title}</h2>
          <p className="mt-1.5 text-[15px] text-text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </motion.div>
      </div>
    </div>
  )
}
