"use client"

import { cn } from "@/lib/utils"
import { ChevronLeft, ChevronRight } from "lucide-react"

export interface Column<T> {
  key: string
  header: string
  className?: string
  render: (row: T) => React.ReactNode
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyFn: (row: T) => string
  page?: number
  pages?: number
  onPageChange?: (page: number) => void
  isLoading?: boolean
  className?: string
}

export function DataTable<T>({
  columns,
  data,
  keyFn,
  page = 1,
  pages = 1,
  onPageChange,
  isLoading,
  className,
}: DataTableProps<T>) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/50">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500",
                    col.className
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-slate-800/50">
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3">
                      <div className="h-4 w-24 animate-pulse rounded bg-slate-800" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-slate-500">
                  No records found
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={keyFn(row)}
                  className="border-b border-slate-800/50 transition-colors hover:bg-slate-900/50"
                >
                  {columns.map((col) => (
                    <td key={col.key} className={cn("px-4 py-3 text-slate-300", col.className)}>
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pages > 1 && onPageChange && (
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 text-slate-400 transition-colors hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-xs text-slate-500">
            {page} / {pages}
          </span>
          <button
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pages}
            className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 text-slate-400 transition-colors hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
