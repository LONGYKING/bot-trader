import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn(
      "flex flex-col items-center justify-center gap-3 py-16 text-center",
      className
    )}>
      {Icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-800">
          <Icon className="h-5 w-5 text-slate-500" />
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-slate-300">{title}</p>
        {description && <p className="text-xs text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}
