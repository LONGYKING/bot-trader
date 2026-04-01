"use client"

import { useQuery } from "@tanstack/react-query"
import { strategies, signals, outcomes } from "@/lib/api"
import { StatCard } from "@/components/shared/stat-card"
import { TrendingUp, Zap, Trophy, BarChart2 } from "lucide-react"
import { fmtPct } from "@/lib/utils"

export function MetricsRow() {
  const { data: strategiesData } = useQuery({
    queryKey: ["strategies", "active"],
    queryFn: () => strategies.list({ is_active: true, page_size: 1 }),
  })

  const { data: signalsData } = useQuery({
    queryKey: ["signals", "today"],
    queryFn: () => {
      const from = new Date()
      from.setHours(0, 0, 0, 0)
      return signals.list({ from_dt: from.toISOString(), page_size: 1 })
    },
  })

  const { data: statsData } = useQuery({
    queryKey: ["outcomes", "stats"],
    queryFn: () => outcomes.stats(),
  })

  const activeStrategies = strategiesData?.total ?? 0
  const signalsToday = signalsData?.total ?? 0
  const winRate = statsData?.win_rate != null ? `${(statsData.win_rate * 100).toFixed(1)}%` : "—"
  const avgPnl = statsData?.avg_pnl_pct != null ? fmtPct(statsData.avg_pnl_pct) : "—"
  const pnlTrend = statsData?.avg_pnl_pct != null
    ? statsData.avg_pnl_pct >= 0 ? "up" : "down"
    : "neutral" as const

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard
        label="Active Strategies"
        value={activeStrategies}
        icon={TrendingUp}
      />
      <StatCard
        label="Signals Today"
        value={signalsToday}
        icon={Zap}
      />
      <StatCard
        label="Win Rate"
        value={winRate}
        icon={Trophy}
        trend={statsData?.win_rate != null ? (statsData.win_rate >= 0.5 ? "up" : "down") : "neutral"}
      />
      <StatCard
        label="Avg PnL"
        value={avgPnl}
        icon={BarChart2}
        trend={pnlTrend}
      />
    </div>
  )
}
