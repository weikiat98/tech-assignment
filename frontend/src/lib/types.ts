import type { Data, Layout } from "plotly.js";

/** Agent event payloads differ per event type and agent; components narrow them where they read them. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type EventContent = Record<string, any>;

export type AnalysisStatus =
  | "queued"
  | "running"
  | "awaiting_input"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

export interface AnalysisSummary {
  id: string;
  query: string;
  status: AnalysisStatus;
  created_at: string;
  finished_at: string | null;
  total_cost_usd: number;
  total_tokens: number;
  chat_id: string | null;
  turn: number;
  version: number;
}

export interface AgentEvent {
  run_id: string;
  seq: number;
  agent: string;
  type: string;
  content: EventContent;
  tokens: number;
  cost_usd: number;
  ts: string;
}

export interface Fact {
  id: string;
  key: string;
  label: string;
  value: number;
  unit: string;
  display: string;
  method: string;
  params: Record<string, string | number | boolean | null | string[]>;
  source_keys: string[];
  derived: boolean;
}

export interface Chart {
  id: string;
  title: string;
  kind: string;
  spec: { data: Data[]; layout: Partial<Layout> };
  fact_ids: string[];
  source_keys: string[];
}

export interface QualityIssue {
  check: string;
  severity: "info" | "warning" | "error";
  message: string;
}

export interface DatasetSummary {
  key: string;
  source_id: string;
  dataset_id: string;
  title: string;
  url: string | null;
  unit: string | null;
  frequency: string | null;
  retrieved_at: string;
  is_fallback: boolean;
  fallback_reason: string | null;
  trust_tier: number;
  agency: string | null;
  footnote: string | null;
  series: string[];
  period_range: [string, string] | null;
  row_count: number;
  quality: { score: number; issues: QualityIssue[]; actions: string[]; row_count: number } | null;
  notes: string[];
}

export interface Claim {
  text: string;
  fact_ids: string[];
  source_keys: string[];
}

export interface Report {
  title: string;
  executive_summary: string;
  key_findings: Claim[];
  sector_analysis: Claim[];
  policy_implications: Claim[];
  limitations: string[];
}

export interface Verification {
  passed: boolean;
  numeric_pass_rate: number;
  citation_pass_rate: number;
  entity_pass_rate: number;
  attempt: number;
  checks: { claim: string; section: string; passed: boolean; problems: string[] }[];
}

export interface ContextNote {
  title: string;
  url: string;
  trust_tier: number;
  excerpt: string;
  injection_flagged: boolean;
}

export interface ResearchIntent {
  topic: string;
  sectors: string[];
  metrics: string[];
  start_year: number | null;
  end_year: number | null;
  analysis_types: string[];
  wants_web_context: boolean;
  uses_internal_data: boolean;
  needs_clarification: boolean;
  confidence: number;
  reasoning: string;
}

export interface AnalysisResult {
  query: string;
  intent: ResearchIntent | null;
  plan: { reasoning: string; tasks: { id: string; agent: string; description: string; source: string }[] } | null;
  report: Report | null;
  verification: Verification | null;
  facts: Fact[];
  charts: Chart[];
  datasets: DatasetSummary[];
  context_notes: ContextNote[];
  warnings: string[];
  fallbacks: string[];
  llm_providers_used: string[];
  total_tokens: number;
  total_cost_usd: number;
  trace_url: string | null;
  markdown: string | null;
  outcome?: string | null;
  /** Short next questions built from the answered intent. */
  suggestions?: string[];
  /** Facts carried over from earlier questions in the chat. */
  carried_fact_ids?: string[];
}

export interface AnalysisDetail extends AnalysisSummary {
  options: { web_context?: boolean; provider_preference?: string | null };
  intent: ResearchIntent | null;
  plan: AnalysisResult["plan"];
  result: AnalysisResult | null;
  error: string | null;
}

export interface RuntimeConfig {
  llm_chain: string[];
  web_search_chain: string[];
  langfuse_enabled: boolean;
  offline_mode: boolean;
  chaos: ChaosState;
}

export interface ChaosState {
  fail_sources: string[];
  fail_llm: string[];
  inject_hallucination: boolean;
  enabled?: boolean;
}

export interface RunSummary {
  status: AnalysisStatus;
  outcome: string | null;
  verified: boolean | null;
  seconds: number | null;
  cost_usd: number;
  models: string[];
  model_calls: Record<string, number>;
  llm_fallbacks: string[];
  steps: number;
  retries: { rewrites: number; replans: number; failed_steps: number };
  sources: { key: string; title: string; agency: string | null; state: "live" | "saved_copy" | "failed"; reason: string | null; quality: number | null }[];
  checks: { numeric_pass_rate: number | null; citation_pass_rate: number | null; entity_pass_rate: number | null };
  facts_from_earlier_questions: number;
  worth_knowing: string[];
  trace_url: string | null;
}

export type ProviderChoice = "auto" | "openai" | "gemini";

export interface ChatSummary {
  id: string;
  title: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
  status: AnalysisStatus | null;
  turns: number;
}

export interface ChatTurn {
  turn: number;
  query: string;
  /** Oldest first; the last one is shown, earlier ones stay reachable. */
  versions: AnalysisSummary[];
}

export interface ChatDetail extends ChatSummary {
  items: ChatTurn[];
}

export type RunActivityPeriod = "week" | "month" | "year";

export interface RunCounts {
  runs: number;
  completed: number;
  failed: number;
  cancelled: number;
  /** Queued, running or waiting for an answer. */
  active: number;
  verified: number;
  cost_usd: number;
}

export interface RunActivityBucket extends RunCounts {
  start: string;
  label: string;
  /** The period as UTC instants, for fetching its runs. */
  from: string;
  to: string;
  /** Every run up to the end of this period. */
  cumulative_runs: number;
}

/** GET /api/v1/activity: newest period first. */
export interface RunActivity {
  period: RunActivityPeriod;
  tz: string;
  totals: RunCounts;
  buckets: RunActivityBucket[];
}

export interface RunActivityRow {
  id: string;
  chat_id: string | null;
  query: string;
  status: AnalysisStatus;
  created_at: string;
  seconds: number | null;
  cost_usd: number;
  verified: boolean | null;
}
