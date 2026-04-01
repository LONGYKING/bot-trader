import { cn, signalColor, signalLabel, signalPrefix } from "@/lib/utils"

interface SignalBadgeProps {
  value: number
  showLabel?: boolean
  className?: string
}

export function SignalBadge({ value, showLabel = false, className }: SignalBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold tabular-nums",
        signalColor(value),
        className
      )}
    >
      {signalPrefix(value)}
      {showLabel && <span className="hidden sm:inline">· {signalLabel(value)}</span>}
    </span>
  )
}
