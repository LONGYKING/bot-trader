import type {
  PaginatedResponse,
  Strategy, StrategyClass, StrategyPerformance, StrategyCreate,
  Signal, SignalForceRequest,
  Channel, ChannelCreate, ChannelTestResponse, Delivery,
  Subscription, SubscriptionCreate,
  Outcome, OutcomeStats,
  Backtest, BacktestTrade, BacktestCreate,
  ApiKey, ApiKeyCreated, ApiKeyCreate, WorkerStats,
} from "./types"

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

// Read JWT access token from the zustand auth store
function getToken(): string {
  if (typeof window === "undefined") return ""
  try {
    const raw = localStorage.getItem("bt_auth")
    if (!raw) return ""
    return JSON.parse(raw)?.state?.accessToken ?? ""
  } catch {
    return ""
  }
}

// Legacy API key fallback (for integrations using X-API-Key)
function getLegacyKey(): string {
  if (typeof window === "undefined") return ""
  try {
    const raw = localStorage.getItem("bt_api_key")
    if (!raw) return ""
    return JSON.parse(raw)?.state?.apiKey ?? ""
  } catch {
    return ""
  }
}

async function req<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const legacyKey = getLegacyKey()

  const authHeader: Record<string, string> = {}
  if (token) {
    authHeader["Authorization"] = `Bearer ${token}`
  } else if (legacyKey) {
    authHeader["X-API-Key"] = legacyKey
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader,
      ...options.headers,
    },
  })

  // Auto-refresh on 401
  if (res.status === 401 && token) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      // Retry the original request with the new token
      const newToken = getToken()
      const retryRes = await fetch(`${BASE}${path}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${newToken}`,
          ...options.headers,
        },
      })
      if (!retryRes.ok) {
        const body = await retryRes.text()
        throw new Error(body || `HTTP ${retryRes.status}`)
      }
      if (retryRes.status === 204) return undefined as T
      return retryRes.json()
    } else {
      // Refresh failed — force logout
      if (typeof window !== "undefined") {
        localStorage.removeItem("bt_auth")
        window.location.href = "/login"
      }
      throw new Error("Session expired. Please log in again.")
    }
  }

  if (!res.ok) {
    const body = await res.text()
    throw new Error(body || `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

async function tryRefresh(): Promise<boolean> {
  try {
    const raw = localStorage.getItem("bt_auth")
    if (!raw) return false
    const refreshToken = JSON.parse(raw)?.state?.refreshToken
    if (!refreshToken) return false

    const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const data = await res.json()

    // Update the stored tokens
    const stored = JSON.parse(raw)
    stored.state.accessToken = data.access_token
    stored.state.refreshToken = data.refresh_token
    localStorage.setItem("bt_auth", JSON.stringify(stored))
    return true
  } catch {
    return false
  }
}

function qs(params: Record<string, unknown>): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ""
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  register: (data: { email: string; password: string; full_name?: string }) =>
    fetch(`${BASE}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      return r.json() as Promise<{ access_token: string; refresh_token: string }>
    }),

  login: (data: { email: string; password: string }) =>
    fetch(`${BASE}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then(async (r) => {
      if (!r.ok) throw new Error(await r.text())
      return r.json() as Promise<{ access_token: string; refresh_token: string }>
    }),

  me: () =>
    req<{
      user: { id: string; email: string; full_name: string | null; is_owner: boolean }
      tenant: { id: string; name: string; plan_key: string; plan_status: string }
      limits: Record<string, unknown>
    }>("/api/v1/auth/me"),
}

// ─── Billing ─────────────────────────────────────────────────────────────────

export const billing = {
  status: () =>
    req<{ plan_key: string; plan_status: string; payment_provider: string | null }>("/api/v1/billing/status"),

  checkout: (data: { plan_key: string; success_url: string; cancel_url: string }) =>
    req<{ checkout_url: string }>("/api/v1/billing/checkout", { method: "POST", body: JSON.stringify(data) }),

  portal: (data: { return_url: string }) =>
    req<{ portal_url: string }>("/api/v1/billing/portal", { method: "POST", body: JSON.stringify(data) }),
}

// ─── Strategies ──────────────────────────────────────────────────────────────

export const strategies = {
  classes: () =>
    req<StrategyClass[]>("/api/v1/strategies/classes"),

  list: (params: { asset?: string; timeframe?: string; is_active?: boolean; strategy_class?: string; page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Strategy>>(`/api/v1/strategies${qs(params)}`),

  get: (id: string) =>
    req<Strategy>(`/api/v1/strategies/${id}`),

  create: (data: StrategyCreate) =>
    req<Strategy>("/api/v1/strategies", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: Partial<StrategyCreate> & { is_active?: boolean }) =>
    req<Strategy>(`/api/v1/strategies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  delete: (id: string) =>
    req<void>(`/api/v1/strategies/${id}`, { method: "DELETE" }),

  signals: (id: string, params: { page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Signal>>(`/api/v1/strategies/${id}/signals${qs(params)}`),

  performance: (id: string) =>
    req<StrategyPerformance>(`/api/v1/strategies/${id}/performance`),
}

// ─── Signals ─────────────────────────────────────────────────────────────────

export const signals = {
  list: (params: { strategy_id?: string; asset?: string; signal_value?: number; from_dt?: string; to_dt?: string; is_profitable?: boolean; page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Signal>>(`/api/v1/signals${qs(params)}`),

  get: (id: string) =>
    req<Signal>(`/api/v1/signals/${id}`),

  force: (data: SignalForceRequest) =>
    req<Signal>("/api/v1/signals/force", { method: "POST", body: JSON.stringify(data) }),
}

// ─── Channels ────────────────────────────────────────────────────────────────

export const channels = {
  list: (params: { page?: number; page_size?: number } = {}) =>
    req<Channel[]>(`/api/v1/channels${qs(params)}`),

  get: (id: string) =>
    req<Channel>(`/api/v1/channels/${id}`),

  create: (data: ChannelCreate) =>
    req<Channel>("/api/v1/channels", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: Partial<ChannelCreate> & { is_active?: boolean }) =>
    req<Channel>(`/api/v1/channels/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  delete: (id: string) =>
    req<void>(`/api/v1/channels/${id}`, { method: "DELETE" }),

  test: (id: string) =>
    req<ChannelTestResponse>(`/api/v1/channels/${id}/test`, { method: "POST" }),

  health: (id: string) =>
    req<unknown>(`/api/v1/channels/${id}/health`),

  deliveries: (id: string, params: { page?: number; page_size?: number } = {}) =>
    req<Delivery[]>(`/api/v1/channels/${id}/deliveries${qs(params)}`),
}

// ─── Subscriptions ────────────────────────────────────────────────────────────

export const subscriptions = {
  list: (params: { channel_id?: string; strategy_id?: string; is_active?: boolean; page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Subscription>>(`/api/v1/subscriptions${qs(params)}`),

  get: (id: string) =>
    req<Subscription>(`/api/v1/subscriptions/${id}`),

  create: (data: SubscriptionCreate) =>
    req<Subscription>("/api/v1/subscriptions", { method: "POST", body: JSON.stringify(data) }),

  update: (id: string, data: { is_active?: boolean }) =>
    req<Subscription>(`/api/v1/subscriptions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  delete: (id: string) =>
    req<void>(`/api/v1/subscriptions/${id}`, { method: "DELETE" }),
}

// ─── Outcomes ─────────────────────────────────────────────────────────────────

export const outcomes = {
  list: (params: { is_profitable?: boolean; asset?: string; strategy_id?: string; from_dt?: string; to_dt?: string; page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Outcome>>(`/api/v1/outcomes${qs(params)}`),

  get: (signalId: string) =>
    req<Outcome>(`/api/v1/outcomes/${signalId}`),

  stats: (params: { asset?: string; strategy_id?: string } = {}) =>
    req<OutcomeStats>(`/api/v1/outcomes/stats${qs(params)}`),

  resolve: () =>
    req<{ message: string; resolved: number }>("/api/v1/outcomes/resolve", { method: "POST" }),
}

// ─── Backtests ───────────────────────────────────────────────────────────────

export const backtests = {
  list: (params: { strategy_id?: string; page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<Backtest>>(`/api/v1/backtests${qs(params)}`),

  get: (id: string) =>
    req<Backtest>(`/api/v1/backtests/${id}`),

  submit: (data: BacktestCreate) =>
    req<Backtest>("/api/v1/backtests", { method: "POST", body: JSON.stringify(data) }),

  trades: (id: string, params: { page?: number; page_size?: number } = {}) =>
    req<PaginatedResponse<BacktestTrade>>(`/api/v1/backtests/${id}/trades${qs(params)}`),
}

// ─── Admin ────────────────────────────────────────────────────────────────────

export const admin = {
  listKeys: () =>
    req<ApiKey[]>("/api/v1/admin/api-keys"),

  createKey: (data: ApiKeyCreate) =>
    req<ApiKeyCreated>("/api/v1/admin/api-keys", { method: "POST", body: JSON.stringify(data) }),

  revokeKey: (id: string) =>
    req<void>(`/api/v1/admin/api-keys/${id}`, { method: "DELETE" }),

  rotateKey: (id: string) =>
    req<ApiKeyCreated>(`/api/v1/admin/api-keys/${id}/rotate`, { method: "POST" }),

  workerStats: () =>
    req<WorkerStats>("/api/v1/admin/workers/stats"),

  listPlans: (publicOnly = false) =>
    req<Record<string, unknown>[]>(`/api/v1/admin/plans${publicOnly ? "?public=true" : ""}`),

  updatePlan: (key: string, data: Record<string, unknown>) =>
    req<Record<string, unknown>>(`/api/v1/admin/plans/${key}`, { method: "PATCH", body: JSON.stringify(data) }),
}
