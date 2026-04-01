"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { strategies } from "@/lib/api"
import type { Strategy } from "@/lib/types"
import { StatusDot } from "@/components/shared/status-dot"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { TrendingUp } from "lucide-react"
import Link from "next/link"

interface StrategyCardProps {
  strategy: Strategy
}

export function StrategyCard({ strategy: s }: StrategyCardProps) {
  const qc = useQueryClient()

  const toggle = useMutation({
    mutationFn: () => strategies.update(s.id, { is_active: !s.is_active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategies"] })
      toast.success(`Strategy ${s.is_active ? "deactivated" : "activated"}`)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const remove = useMutation({
    mutationFn: () => strategies.delete(s.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategies"] })
      toast.success("Strategy deleted")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 flex flex-col gap-4 hover:border-slate-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <Link
              href={`/strategies/${s.id}`}
              className="text-sm font-semibold text-slate-100 hover:text-emerald-400 transition-colors"
            >
              {s.name}
            </Link>
            <p className="text-xs text-slate-500">{s.strategy_class}</p>
          </div>
        </div>
        <StatusDot status={s.is_active ? "active" : "inactive"} />
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        {[
          { label: "Asset", value: s.asset },
          { label: "Timeframe", value: s.timeframe },
          { label: "Exchange", value: s.exchange },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg bg-slate-800/60 px-2 py-2">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="text-sm font-medium text-slate-200 truncate">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-2 mt-auto">
        <button
          onClick={() => toggle.mutate()}
          disabled={toggle.isPending}
          className={cn(
            "flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors",
            s.is_active
              ? "bg-slate-800 text-slate-300 hover:bg-slate-700"
              : "bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30"
          )}
        >
          {s.is_active ? "Deactivate" : "Activate"}
        </button>
        <button
          onClick={() => {
            if (confirm(`Delete "${s.name}"?`)) remove.mutate()
          }}
          disabled={remove.isPending}
          className="flex-1 rounded-lg bg-rose-500/10 py-1.5 text-xs font-semibold text-rose-400 hover:bg-rose-500/20 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
