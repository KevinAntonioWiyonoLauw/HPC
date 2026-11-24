// api.ts - klien tipis ke FastAPI SIKA (via proxy /api)
const BASE = "/api";

export interface Status {
  engine_active: string;
  engines: string[];
  source: string;
  n: number;
  dim: number;
  corpus: string | null;
  load_mode?: string;
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

export interface DocItem {
  name: string;
  title: string;
  pasal: number;
  size: number;
  modified: number;
}

export interface DocsList {
  dir: string;
  count: number;
  documents: DocItem[];
}

export interface ReindexStatus {
  running: boolean;
  last: { ok: boolean; tail: string; at: number } | null;
}

export interface CacheStats {
  embed_entries: number;
  retr_entries: number;
  embed_cap: number;
  retr_cap: number;
}

export interface QueueStat {
  queue_depth: number;
  max_queue_depth: number;
  total_waits: number;
  avg_wait_ms: number;
}

export interface QueueStats {
  engine: QueueStat;
  embed: QueueStat;
  engine_limit: number;
  embed_limit: number;
}

// Kejadian streaming dari POST /ask/stream (SSE).
export type AskStreamEvent =
  | { type: "citations"; engine: string; cached: boolean; retrieval_ms: number; citations: Neighbor[] }
  | { type: "delta"; text: string }
  | { type: "done"; llm_status: string; llm_ms?: number; total_ms?: number };

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
  // Streaming SSE: panggil onEvent untuk tiap kejadian. Return fungsi untuk abort.
  askStream: (
    query: string,
    k: number,
    use_llm: boolean,
    onEvent: (e: AskStreamEvent) => void,
  ): (() => void) => {
    const ctrl = new AbortController();
    (async () => {
      const r = await fetch(BASE + "/ask/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, k, use_llm }),
        signal: ctrl.signal,
      });
      if (!r.ok || !r.body) throw new Error(`${r.status}: ${await r.text()}`);
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          try {
            onEvent(JSON.parse(line.slice(5).trim()) as AskStreamEvent);
          } catch {
            /* abaikan baris tak valid */
          }
        }
      }
    })().catch((e) => {
      if ((e as any)?.name !== "AbortError") onEvent({ type: "done", llm_status: `error: ${e}` });
    });
    return () => ctrl.abort();
  },
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
  documents: () => j<DocsList>("/documents"),
  uploadDocument: (payload: { name: string; content: string; title?: string; year?: string; unit?: string }) =>
    j<{ ok: boolean; document: DocItem }>("/documents", { method: "POST", body: JSON.stringify(payload) }),
  deleteDocument: (name: string) =>
    j<{ ok: boolean; deleted: string }>(`/documents/${encodeURIComponent(name)}`, { method: "DELETE" }),
  reindexDocuments: () =>
    j<{ ok: boolean; started: boolean }>("/documents/reindex", { method: "POST" }),
  reindexStatus: () => j<ReindexStatus>("/documents/reindex/status"),
  cacheStats: () => j<CacheStats>("/cache/stats"),
  clearCache: () =>
    j<{ ok: boolean; embed_entries: number; retr_entries: number }>("/cache/clear", { method: "POST" }),
  queueStats: () => j<QueueStats>("/queue/stats"),
};
