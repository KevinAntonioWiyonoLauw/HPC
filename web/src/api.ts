// api.ts - klien tipis ke FastAPI SIKA (via proxy /api)
const BASE = "/api";

export interface Status {
  engine_active: string;
  engines: string[];
  source: string;
  n: number;
  dim: number;
  corpus: string | null;
  llm: { base_url: string; model: string; api_key: string };
}

export interface Neighbor {
  rank: number;
  index: number;
  dist2: number;
  distance: number;
  text: string;
  meta: { sop?: string; judul?: string; pasal?: string; tahun?: number; unit?: string };
}

export interface SearchResp {
  engine: string;
  k: number;
  retrieval_ms: number;
  cached: boolean;
  results: Neighbor[];
}

export interface AskResp {
  query: string;
  answer: string;
  citations: Neighbor[];
  engine: string;
  cached: boolean;
  latency: { embed_ms: number; retrieval_ms: number; llm_ms: number; total_ms: number };
  llm_status: string;
}

export interface BenchResp {
  engine: string;
  n: number;
  k: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  mean_ms: number;
  std_ms?: number;
  qps: number;
  qps_mean?: number;
  qps_std?: number;
  qps_cov?: number;
  reps?: number;
  warmup?: number;
  qps_runs?: number[];
  error?: string;
}

export interface LLMConfig {
  base_url: string;
  model: string;
  api_key: string;
  max_tokens: number;
  timeout_s: number;
}

async function j<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`${r.status}: ${txt}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  status: () => j<Status>("/status"),
  engines: () => j<{ engines: string[]; active: string }>("/engines"),
  setEngine: (name: string) =>
    j<{ active: string }>("/engine", { method: "POST", body: JSON.stringify({ name }) }),
  search: (query: string, k = 10, engine?: string) =>
    j<SearchResp>("/search", { method: "POST", body: JSON.stringify({ query, k, engine }) }),
  ask: (query: string, k = 10, use_llm = true) =>
    j<AskResp>("/ask", { method: "POST", body: JSON.stringify({ query, k, use_llm }) }),
  bench: (query: string, n = 100, k = 10, engine?: string) =>
    j<BenchResp>("/bench", { method: "POST", body: JSON.stringify({ query, n, k, engine }) }),
  compare: async (query: string, n = 100, k = 10): Promise<BenchResp[]> => {
    // Benchmark adil di sisi server: embedding sekali, tiap engine dapat warmup +
    // ulangan yang sama, statistik median lintasan. Menghindari variasi antar-run
    // akibat memanggil /bench terpisah untuk tiap engine.
    const r = await j<{ results: BenchResp[] }>("/bench/compare", {
      method: "POST",
      body: JSON.stringify({ query, n, k, reps: 3, warmup: 20 }),
    });
    return r.results.filter((x) => !x.error);
  },
  getConfig: () => j<LLMConfig>("/config"),
  setConfig: (c: Partial<LLMConfig>) =>
    j<LLMConfig>("/config", { method: "POST", body: JSON.stringify(c) }),
  models: () => j<{ models: string[]; current: string }>("/models"),
};
