import { cn, statusColor } from "@/lib/utils"

interface StatusDotProps {
  status: string
  label?: string
  className?: string
}

export function StatusDot({ status, label, className }: StatusDotProps) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span className={cn("h-2 w-2 rounded-full shrink-0", statusColor(status))} />
      {label && <span className="text-xs text-slate-400">{label}</span>}
    </span>
  )
}
