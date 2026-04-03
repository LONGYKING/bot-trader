"use client"

import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { CheckCircle2, Zap } from "lucide-react"
import { admin, billing } from "@/lib/api"
import { useAuthStore } from "@/hooks/use-auth"

function formatPrice(cents: number) {
  if (cents === 0) return "Free"
  return `$${(cents / 100).toFixed(0)}/mo`
}

export default function PricingPage() {
  const router = useRouter()
  const tenant = useAuthStore((s) => s.tenant)

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ["public-plans"],
    queryFn: () => admin.listPlans(true),
  })

  const handleUpgrade = async (planKey: string) => {
    if (!tenant) { router.push("/register"); return }
    try {
      const { checkout_url } = await billing.checkout({
        plan_key: planKey,
        success_url: `${window.location.origin}/?upgraded=true`,
        cancel_url: `${window.location.origin}/pricing`,
      })
      window.location.href = checkout_url
    } catch (e) {
      console.error(e)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 px-6 py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-12 text-center">
          <h1 className="text-3xl font-bold text-slate-100">Simple, transparent pricing</h1>
          <p className="mt-3 text-slate-400">Start free. Upgrade when you&apos;re ready.</p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const key = plan.key as string
            const isCurrent = tenant?.plan_key === key
            const isPopular = key === "pro"

            return (
              <div
                key={key}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  isPopular
                    ? "border-emerald-500 bg-slate-900"
                    : "border-slate-800 bg-slate-900"
                }`}
              >
                {isPopular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="flex items-center gap-1 rounded-full bg-emerald-500 px-3 py-0.5 text-xs font-semibold text-slate-950">
                      <Zap className="h-3 w-3" /> Popular
                    </span>
                  </div>
                )}

                <div className="mb-4">
                  <h2 className="text-base font-semibold text-slate-100">
                    {plan.display_name as string}
                  </h2>
                  <p className="mt-1 text-3xl font-bold text-slate-100">
                    {formatPrice(plan.price_monthly_cents as number)}
                  </p>
                  {plan.description != null && (
                    <p className="mt-2 text-xs text-slate-400">{String(plan.description)}</p>
                  )}
                </div>

                <ul className="mb-6 flex-1 space-y-2 text-xs text-slate-400">
                  <PlanFeature
                    label={`${(plan.max_strategies as number) === -1 ? "Unlimited" : plan.max_strategies} strategies`}
                  />
                  <PlanFeature
                    label={`${(plan.max_channels as number) === -1 ? "Unlimited" : plan.max_channels} channels`}
                  />
                  <PlanFeature
                    label={
                      (plan.max_signals_per_day as number) === -1
                        ? "Unlimited signals/day"
                        : `${plan.max_signals_per_day} signals/day`
                    }
                  />
                  <PlanFeature
                    label={
                      (plan.max_backtests_per_month as number) === -1
                        ? "Unlimited backtests"
                        : `${plan.max_backtests_per_month} backtests/month`
                    }
                  />
                  {(plan.can_use_exchange_channels as boolean) && (
                    <PlanFeature label="Live exchange trading" />
                  )}
                  {(plan.can_create_api_keys as boolean) && (
                    <PlanFeature label="API key integrations" />
                  )}
                </ul>

                <button
                  onClick={() => handleUpgrade(key)}
                  disabled={isCurrent}
                  className={`w-full rounded-lg py-2 text-sm font-semibold transition-colors ${
                    isCurrent
                      ? "cursor-default border border-slate-700 bg-transparent text-slate-500"
                      : isPopular
                      ? "bg-emerald-500 text-slate-950 hover:bg-emerald-400"
                      : "border border-slate-700 text-slate-300 hover:border-emerald-500 hover:text-emerald-400"
                  }`}
                >
                  {isCurrent ? "Current plan" : key === "free" ? "Get started" : "Upgrade"}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function PlanFeature({ label }: { label: string }) {
  return (
    <li className="flex items-center gap-2">
      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
      {label}
    </li>
  )
}
