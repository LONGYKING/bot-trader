// ─── Common ─────────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ─── Strategies ─────────────────────────────────────────────────────────────

export interface StrategyRiskConfig {
  max_risk_per_trade_pct?: number | null
  max_daily_loss_pct?: number | null
  cooldown_minutes?: number | null
}

export interface Strategy {
  id: string
  name: string
  strategy_class: string
  description?: string | null
  asset: string
  timeframe: string
  exchange: string
  params: Record<string, unknown>
  trade_type: string
  execution_params: Record<string, unknown>
  interval_minutes: number
  risk_config: StrategyRiskConfig
  is_active: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface StrategyClass {
  name: string
  description: string
}

export interface StrategyPerformance {
  strategy_id: string
  total_signals: number
  profitable_signals: number
  win_rate: number
  avg_pnl_pct: number
  by_regime: Record<string, unknown>
}

export interface StrategyCreate {
  name: string
  strategy_class: string
  description?: string
  asset: string
  timeframe: string
  exchange?: string
  trade_type?: string
  params?: Record<string, unknown>
  interval_minutes?: number
}

// ─── Signals ────────────────────────────────────────────────────────────────

export interface Signal {
  id: string
  strategy_id: string
  asset: string
  timeframe: string
  signal_value: number
  direction?: string | null
  tenor_days?: number | null
  confidence?: number | null
  regime?: string | null
  entry_price?: number | null
  entry_time: string
  expiry_time?: string | null
  indicator_snapshot?: Record<string, unknown> | null
  rule_triggered?: string | null
  is_profitable?: boolean | null
  created_at: string
}

export interface SignalForceRequest {
  strategy_id: string
  signal_value?: number
  entry_price?: number | null
}

// ─── Channels ────────────────────────────────────────────────────────────────

export interface Channel {
  id: string
  name: string
  channel_type: string
  config: Record<string, unknown>
  is_active: boolean
  last_health_check?: string | null
  health_status?: string | null
  created_at: string
}

export interface ChannelCreate {
  name: string
  channel_type: string
  config: Record<string, unknown>
}

export interface ChannelTestResponse {
  success: boolean
  message: string
}

export interface Delivery {
  id: string
  signal_id: string
  channel_id: string
  status: string
  attempt_count: number
  delivered_at?: string | null
  last_attempt_at?: string | null
  external_msg_id?: string | null
  error_message?: string | null
  delivery_metadata?: Record<string, unknown> | null
  created_at: string
}

// ─── Subscriptions ──────────────────────────────────────────────────────────

export interface SubscriptionPreferences {
  quiet_hours?: { start: string; end: string; timezone: string } | null
  max_signals_per_hour?: number | null
  delivery_delay_seconds?: number
}

export interface Subscription {
  id: string
  channel_id: string
  strategy_id?: string | null
  asset_filter?: string[] | null
  signal_filter?: number[] | null
  min_confidence: number
  preferences: SubscriptionPreferences
  is_active: boolean
  created_at: string
}

export interface SubscriptionCreate {
  channel_id: string
  strategy_id?: string | null
  asset_filter?: string[] | null
  signal_filter?: number[] | null
  min_confidence?: number
}

// ─── Outcomes ────────────────────────────────────────────────────────────────

export interface Outcome {
  id: string
  signal_id: string
  exit_price?: number | null
  exit_time?: string | null
  pnl_pct?: number | null
  is_profitable?: boolean | null
  computed_at: string
}

export interface OutcomeStats {
  total_count: number
  winning_count: number
  win_rate: number
  avg_pnl_pct: number
}

// ─── Backtests ───────────────────────────────────────────────────────────────

export interface Backtest {
  id: string
  strategy_id: string
  status: string
  date_from: string
  date_to: string
  initial_capital: number
  total_trades?: number | null
  winning_trades?: number | null
  win_rate?: number | null
  total_pnl_pct?: number | null
  sharpe_ratio?: number | null
  max_drawdown_pct?: number | null
  annual_return_pct?: number | null
  sheets_url?: string | null
  error_message?: string | null
  created_at: string
  completed_at?: string | null
}

export interface BacktestTrade {
  id: string
  backtest_id: string
  entry_time: string
  exit_time: string
  direction: string
  tenor_days?: number | null
  entry_price: number
  exit_price: number
  pnl_pct: number
  capital_before?: number | null
  capital_after?: number | null
}

export interface BacktestCreate {
  strategy_id: string
  date_from: string
  date_to: string
  initial_capital?: number
}

// ─── Admin ───────────────────────────────────────────────────────────────────

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  scopes: string[]
  is_active: boolean
  last_used_at?: string | null
  expires_at?: string | null
  created_at: string
}

export interface ApiKeyCreated extends ApiKey {
  raw_key: string
}

export interface ApiKeyCreate {
  name: string
  scopes?: string[]
  expires_at?: string | null
}

export interface WorkerStats {
  status: string
  message: string
}
