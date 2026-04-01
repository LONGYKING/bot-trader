import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, formatDistanceToNow } from "date-fns"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ─── Signal helpers ──────────────────────────────────────────────────────────

export type SignalValue = -7 | -3 | 0 | 3 | 7

export function signalLabel(v: number): string {
  switch (v) {
    case 7:  return "Strong Buy"
    case 3:  return "Buy"
    case -3: return "Sell"
    case -7: return "Strong Sell"
    default: return "Neutral"
  }
}

export function signalColor(v: number): string {
  switch (v) {
    case 7:  return "text-emerald-400 bg-emerald-500/15 border-emerald-500/30"
    case 3:  return "text-teal-400 bg-teal-500/15 border-teal-500/30"
    case -3: return "text-amber-400 bg-amber-500/15 border-amber-500/30"
    case -7: return "text-rose-400 bg-rose-500/15 border-rose-500/30"
    default: return "text-slate-400 bg-slate-500/15 border-slate-500/30"
  }
}

export function signalPrefix(v: number): string {
  return v > 0 ? `+${v}` : `${v}`
}

// ─── Date helpers ────────────────────────────────────────────────────────────

export function fmtDate(iso: string): string {
  return format(new Date(iso), "MMM d, yyyy HH:mm")
}

export function fmtDateShort(iso: string): string {
  return format(new Date(iso), "MMM d HH:mm")
}

export function fmtAgo(iso: string): string {
  return formatDistanceToNow(new Date(iso), { addSuffix: true })
}

// ─── Number helpers ──────────────────────────────────────────────────────────

export function fmtPct(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "—"
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(decimals)}%`
}

export function fmtNumber(v: number | null | undefined, decimals = 4): string {
  if (v == null) return "—"
  return v.toLocaleString(undefined, { maximumFractionDigits: decimals })
}

export function pnlColor(v: number | null | undefined): string {
  if (v == null) return "text-slate-400"
  return v >= 0 ? "text-emerald-400" : "text-rose-400"
}

// ─── Status helpers ──────────────────────────────────────────────────────────

export function statusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "active":
    case "sent":
    case "completed":
    case "healthy":
      return "bg-emerald-500"
    case "pending":
    case "retrying":
    case "running":
      return "bg-amber-500"
    case "failed":
    case "dlq":
    case "error":
    case "unhealthy":
      return "bg-rose-500"
    default:
      return "bg-slate-500"
  }
}

export function backtestStatusBadge(status: string): string {
  switch (status) {
    case "completed": return "text-emerald-400 bg-emerald-500/15"
    case "running":   return "text-amber-400 bg-amber-500/15"
    case "failed":    return "text-rose-400 bg-rose-500/15"
    default:          return "text-slate-400 bg-slate-500/15"
  }
}

// ─── Channel type icons ──────────────────────────────────────────────────────

export function channelTypeLabel(type: string): string {
  const map: Record<string, string> = {
    telegram: "Telegram",
    slack: "Slack",
    discord: "Discord",
    whatsapp: "WhatsApp",
    email: "Email",
    webhook: "Webhook",
    exchange: "Exchange",
  }
  return map[type] ?? type
}
