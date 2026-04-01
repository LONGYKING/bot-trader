import { MetricsRow } from "@/components/dashboard/metrics-row"
import { RecentSignals } from "@/components/dashboard/recent-signals"
import { OutcomeChart } from "@/components/dashboard/outcome-chart"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <MetricsRow />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RecentSignals />
        <OutcomeChart />
      </div>
    </div>
  )
}
