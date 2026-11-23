import { useEffect, useState } from "react";
import { api, AskResp, BenchResp, LLMConfig, Status } from "./api";

function fmt(n: number) {
  return n.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [engine, setEngine] = useState<string>("baseline");
  const [engines, setEngines] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [k, setK] = useState(10);
  const [useLlm, setUseLlm] = useState(true);
  const [answer, setAnswer] = useState<AskResp | null>(null);
  const [bench, setBench] = useState<BenchResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [benchLoading, setBenchLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  async function refreshStatus() {
    try {
      const s = await api.status();
      setStatus(s);
      setEngine(s.engine_active);
      setEngines(s.engines);
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  }

  useEffect(() => {
    refreshStatus();
  }, []);

  async function onSwapEngine(name: string) {
    setErr(null);
    try {
      const r = await api.setEngine(name);
      setEngine(r.active);
      await refreshStatus();
    } catch (e: any) {
      setErr(String(e.message || e));
    }
  }

  async function onAsk() {
    if (!query.trim()) return;
    setErr(null);
    setLoading(true);
    setAnswer(null);
    try {
      const r = await api.ask(query, k, useLlm);
      setAnswer(r);
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function onBench() {
    if (!query.trim()) return;
    setErr(null);
    setBenchLoading(true);
    try {
      const r = await api.bench(query, 100, k);
      setBench(r);
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBenchLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <div>
          <h1>SIKA</h1>
          <p className="sub">Asisten Kepatuhan Internal · Exact k-NN (HPC)</p>
        </div>
        <div className="statusbar">
          {status && (
            <>
              <span className="badge">corpus: {status.corpus ?? status.source}</span>
              <span className="badge">N={fmt(status.n)} · D={status.dim}</span>
              <span className="badge mono">LLM: {status.llm.model}</span>
            </>
          )}
          <button className="btn ghost" onClick={() => setShowSettings(true)}>
            ⚙ Provider
          </button>
        </div>
      </header>

      <section className="panel">
        <div className="engines">
          <span className="label">Engine aktif:</span>
          {engines.map((e) => (
            <button
              key={e}
              className={`btn engine ${e === engine ? "active" : ""}`}
              onClick={() => onSwapEngine(e)}
            >
              {e}
            </button>
          ))}
        </div>

        <div className="queryrow">
          <input
            className="query"
            placeholder="Contoh: Apakah pembelian lisensi perangkat lunak 40 juta perlu dua penawaran pembanding?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onAsk()}
          />
          <label className="kfield">
            k
            <input
              type="number"
              min={1}
              max={100}
              value={k}
              onChange={(e) => setK(parseInt(e.target.value || "10"))}
            />
          </label>
          <label className="toggle">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
            LLM
          </label>
          <button className="btn primary" onClick={onAsk} disabled={loading}>
            {loading ? "…" : "Tanya"}
          </button>
          <button className="btn" onClick={onBench} disabled={benchLoading}>
            {benchLoading ? "…" : "Bench 100×"}
          </button>
        </div>

        {err && <div className="error">{err}</div>}
      </section>

      <div className="grid">
        <section className="panel result">
          <h2>Jawaban</h2>
          {!answer && <p className="muted">Belum ada jawaban.</p>}
          {answer && (
            <>
              <div className="answer">{answer.answer}</div>
              <div className="llmstatus">status LLM: {answer.llm_status}</div>
              <h3>Kutipan pasal</h3>
              <ol className="citations">
                {answer.citations.map((c) => (
                  <li key={c.rank}>
                    <div className="cit-head">
                      <strong>
                        {c.meta.sop} {c.meta.pasal}
                      </strong>
                      <span className="muted">
                        {" "}
                        · {c.meta.judul} ({c.meta.tahun}) · unit {c.meta.unit} · jarak{" "}
                        {c.distance.toFixed(4)}
                      </span>
                    </div>
                    <div className="cit-text">{c.text}</div>
                  </li>
                ))}
              </ol>
            </>
          )}
        </section>

        <aside className="panel telemetry">
          <h2>Telemetri</h2>
          {answer && (
            <table className="tbl">
              <tbody>
                <tr>
                  <td>Embedding</td>
                  <td>{fmt(answer.latency.embed_ms)} ms</td>
                </tr>
                <tr className="hl">
                  <td>Retrieval ({answer.engine})</td>
                  <td>{fmt(answer.latency.retrieval_ms)} ms</td>
                </tr>
                <tr>
                  <td>LLM</td>
                  <td>{fmt(answer.latency.llm_ms)} ms</td>
                </tr>
                <tr>
                  <td>Total</td>
                  <td>{fmt(answer.latency.total_ms)} ms</td>
                </tr>
              </tbody>
            </table>
          )}
          {!answer && <p className="muted">Jalankan query untuk melihat latensi per tahap.</p>}

          <h2>Beban 100 query</h2>
          {!bench && <p className="muted">Klik “Bench 100×”.</p>}
          {bench && (
            <table className="tbl">
              <tbody>
                <tr>
                  <td>Engine</td>
                  <td>{bench.engine}</td>
                </tr>
                <tr>
                  <td>p50</td>
                  <td>{fmt(bench.p50_ms)} ms</td>
                </tr>
                <tr className="hl">
                  <td>p95</td>
                  <td>{fmt(bench.p95_ms)} ms</td>
                </tr>
                <tr>
                  <td>p99</td>
                  <td>{fmt(bench.p99_ms)} ms</td>
                </tr>
                <tr>
                  <td>QPS</td>
                  <td>{fmt(bench.qps)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </aside>
      </div>

      {showSettings && (
        <SettingsModal
          initial={status?.llm}
          onClose={() => setShowSettings(false)}
          onSaved={() => {
            setShowSettings(false);
            refreshStatus();
          }}
        />
      )}
    </div>
  );
}

function SettingsModal({
  initial,
  onClose,
  onSaved,
}: {
  initial?: { base_url: string; model: string; api_key: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const [cfg, setCfg] = useState<LLMConfig>({
    base_url: initial?.base_url ?? "http://localhost:12800/v1",
    model: initial?.model ?? "",
    api_key: "",
    max_tokens: 512,
    timeout_s: 60,
  });
  const [models, setModels] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api
      .getConfig()
      .then((c) => setCfg((prev) => ({ ...prev, ...c, api_key: "" })))
      .catch(() => {});
  }, []);

  async function fetchModels() {
    setBusy(true);
    setMsg(null);
    try {
      // kirim kredensial sementara bila diisi
      if (cfg.api_key || cfg.base_url) await api.setConfig({ base_url: cfg.base_url, api_key: cfg.api_key });
      const r = await api.models();
      setModels(r.models);
      setMsg(`${r.models.length} model ditemukan`);
    } catch (e: any) {
      setMsg("Gagal fetch model: " + String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const patch: Partial<LLMConfig> = { base_url: cfg.base_url, model: cfg.model, max_tokens: cfg.max_tokens, timeout_s: cfg.timeout_s };
      if (cfg.api_key) patch.api_key = cfg.api_key;
      await api.setConfig(patch);
      onSaved();
    } catch (e: any) {
      setMsg("Gagal simpan: " + String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Provider LLM (OpenAI-compatible)</h2>
        <label>
          Base URL
          <input value={cfg.base_url} onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })} />
        </label>
        <label>
          API Key
          <input
            type="password"
            placeholder="(kosongkan untuk mempertahankan)"
            value={cfg.api_key}
            onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })}
          />
        </label>
        <div className="row">
          <button className="btn" onClick={fetchModels} disabled={busy}>
            Fetch Models
          </button>
          {models.length > 0 ? (
            <select value={cfg.model} onChange={(e) => setCfg({ ...cfg, model: e.target.value })}>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          ) : (
            <input placeholder="model id" value={cfg.model} onChange={(e) => setCfg({ ...cfg, model: e.target.value })} />
          )}
        </div>
        <div className="row">
          <label className="inline">
            max_tokens
            <input type="number" value={cfg.max_tokens} onChange={(e) => setCfg({ ...cfg, max_tokens: parseInt(e.target.value || "512") })} />
          </label>
          <label className="inline">
            timeout (s)
            <input type="number" value={cfg.timeout_s} onChange={(e) => setCfg({ ...cfg, timeout_s: parseFloat(e.target.value || "60") })} />
          </label>
        </div>
        {msg && <div className="msg">{msg}</div>}
        <div className="row end">
          <button className="btn ghost" onClick={onClose}>
            Batal
          </button>
          <button className="btn primary" onClick={save} disabled={busy}>
            Simpan
          </button>
        </div>
      </div>
    </div>
  );
}
