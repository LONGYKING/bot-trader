"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, TrendingUp, Zap, Radio, Link2,
  BarChart2, FlaskConical, KeyRound, Bot,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/",              label: "Dashboard",     icon: LayoutDashboard },
  { href: "/strategies",    label: "Strategies",    icon: TrendingUp },
  { href: "/signals",       label: "Signals",       icon: Zap },
  { href: "/channels",      label: "Channels",      icon: Radio },
  { href: "/subscriptions", label: "Subscriptions", icon: Link2 },
  { href: "/outcomes",      label: "Outcomes",      icon: BarChart2 },
  { href: "/backtests",     label: "Backtests",     icon: FlaskConical },
  { href: "/admin",         label: "Admin",         icon: KeyRound },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-56 flex-col border-r border-slate-800 bg-slate-950">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-slate-800">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500">
          <Bot className="h-4 w-4 text-slate-950" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-slate-100">
          BotTrader
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        <ul className="space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href)
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-slate-800 text-emerald-400"
                      : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                  )}
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-800 px-4 py-3">
        <p className="text-xs text-slate-600">v1.0 · API Connected</p>
      </div>
    </aside>
  )
}
