"use client"

import { usePathname, useRouter } from "next/navigation"
import { LogOut } from "lucide-react"
import { useAuthStore } from "@/hooks/use-auth"
import { useState } from "react"

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/strategies": "Strategies",
  "/signals": "Signal Feed",
  "/channels": "Channels",
  "/subscriptions": "Subscriptions",
  "/outcomes": "Outcomes",
  "/backtests": "Backtests",
  "/admin": "Admin",
}

export function Header() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, tenant, logout } = useAuthStore()
  const [showMenu, setShowMenu] = useState(false)

  const title = Object.entries(TITLES).find(([k]) =>
    k === "/" ? pathname === "/" : pathname.startsWith(k)
  )?.[1] ?? "BotTrader"

  const handleLogout = () => {
    logout()
    setShowMenu(false)
    router.replace("/login")
  }

  return (
    <header className="fixed top-0 right-0 left-56 z-30 flex h-14 items-center justify-between border-b border-slate-800 bg-slate-950/80 backdrop-blur px-6">
      <h1 className="text-sm font-semibold text-slate-100">{title}</h1>

      <div className="flex items-center gap-2">
        {tenant && (
          <span className="text-xs text-slate-500 capitalize">{tenant.plan_key} plan</span>
        )}
        <div className="relative">
          <button
            onClick={() => setShowMenu((v) => !v)}
            className="flex h-8 items-center gap-2 rounded-md px-2 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
            title="Account"
          >
            <span className="text-xs">{user?.email ?? ""}</span>
          </button>

          {showMenu && (
            <div className="absolute right-0 top-10 w-44 rounded-lg border border-slate-700 bg-slate-900 py-1 shadow-xl">
              <button
                onClick={handleLogout}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
