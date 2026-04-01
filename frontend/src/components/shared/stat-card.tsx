import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  icon?: LucideIcon
  trend?: "up" | "down" | "neutral"
  className?: string
}

export function StatCard({ label, value, sub, icon: Icon, trend, className }: StatCardProps) {
  const trendColor =
    trend === "up" ? "text-emerald-400" :
    trend === "down" ? "text-rose-400" :
    "text-slate-400"

  return (
    <div className={cn(
      "rounded-xl border border-slate-800 bg-slate-900 p-5 flex flex-col gap-3",
      className
    )}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">{label}</span>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
            <Icon className="h-4 w-4 text-slate-400" />
          </div>
        )}
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-slate-100 tabular-nums">{value}</span>
        {sub && <span className={cn("mb-0.5 text-xs font-medium", trendColor)}>{sub}</span>}
      </div>
    </div>
  )
}
