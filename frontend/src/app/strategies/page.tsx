"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { strategies } from "@/lib/api"
import { StrategyCard } from "@/components/strategies/strategy-card"
import { CreateStrategyDialog } from "@/components/strategies/create-strategy-dialog"
import { EmptyState } from "@/components/shared/empty-state"
import { TrendingUp, Plus } from "lucide-react"

export default function StrategiesPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)

  const { data, isLoading } = useQuery({
    queryKey: ["strategies", { is_active: activeFilter }],
    queryFn: () => strategies.list({ is_active: activeFilter, page_size: 50 }),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {[
            { label: "All", value: undefined },
            { label: "Active", value: true },
            { label: "Inactive", value: false },
          ].map(({ label, value }) => (
            <button
              key={label}
              onClick={() => setActiveFilter(value)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeFilter === value
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Strategy
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      ) : !data?.items.length ? (
        <EmptyState
          icon={TrendingUp}
          title="No strategies"
          description="Create your first strategy to get started"
          action={
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
            >
              Create Strategy
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.items.map((s) => (
            <StrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      )}

      <CreateStrategyDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  )
}
