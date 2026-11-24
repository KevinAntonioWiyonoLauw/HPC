import { useEffect, useState } from "react";
import {
  Activity, ArrowRight, BarChart3, BookOpen, Boxes, FileText, Gauge,
  Layers, Loader2, Moon, Network, Search, Server, Settings, Sun, Trophy,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ResponsiveContainer,
  Tooltip as RTooltip, XAxis, YAxis,
} from "recharts";

import { api, AskResp, BenchResp, LLMConfig, Neighbor, Status } from "./api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Card, CardContent, CardDescription, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

function fmt(n: number, d = 2) {
  return n.toLocaleString("id-ID", { maximumFractionDigits: d });
}

const ENGINE_ICON: Record<string, React.ReactNode> = {
  baseline: <Server className="h-3.5 w-3.5" />,
  openmp: <Layers className="h-3.5 w-3.5" />,
  cuda: <Boxes className="h-3.5 w-3.5" />,
  mpi: <Network className="h-3.5 w-3.5" />,
};
const ENGINE_COLOR: Record<string, string> = {
  baseline: "#94a3b8",
  openmp: "#a855f7",
  cuda: "#22c55e",
  mpi: "#f59e0b",
};

export default function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [engine, setEngine] = useState("baseline");
  const [engines, setEngines] = useState<string[]>([]);
  const [query, setQuery] = useState(
    "Apakah pembelian lisensi perangkat lunak senilai 40 juta memerlukan dua penawaran pembanding?"
  );
  const [k, setK] = useState(10);
  const [useLlm, setUseLlm] = useState(true);
  const [answer, setAnswer] = useState<AskResp | null>(null);
  const [bench, setBench] = useState<BenchResp | null>(null);
  const [compare, setCompare] = useState<BenchResp[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [benchLoading, setBenchLoading] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [dark, setDark] = useState(false);

  async function refreshStatus() {
    try {
      const s = await api.status();
      setStatus(s);
      setEngine(s.engine_active);
      setEngines(s.engines);
    } catch (e: any) {
      toast.error("Gagal memuat status", { description: String(e.message || e) });
    }
  }

  useEffect(() => {
    refreshStatus();
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  // Deep-link demo: ?demo=compare otomatis menjalankan perbandingan engine.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("demo") === "compare") {
      const t = setTimeout(() => onCompare(), 400);
      return () => clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSwapEngine(name: string) {
    try {
      const r = await api.setEngine(name);
      setEngine(r.active);
      toast.success(`Engine → ${r.active}`);
      refreshStatus();
    } catch (e: any) {
      toast.error("Gagal tukar engine", { description: String(e.message || e) });
    }
  }

  async function onAsk() {
    if (!query.trim()) return;
    setLoading(true);
    setAnswer(null);
    try {
      setAnswer(await api.ask(query, k, useLlm));
    } catch (e: any) {
      toast.error("Permintaan gagal", { description: String(e.message || e) });
    } finally {
      setLoading(false);
    }
  }

  async function onBench() {
    if (!query.trim()) return;
    setBenchLoading(true);
    try {
      const r = await api.bench(query, 100, k);
      setBench(r);
      toast.success(`Bench ${r.engine}: p95 ${fmt(r.p95_ms)} ms`);
    } catch (e: any) {
      toast.error("Bench gagal", { description: String(e.message || e) });
    } finally {
      setBenchLoading(false);
    }
  }

  async function onCompare() {
    if (!query.trim()) return;
    setCompareLoading(true);
    setCompare(null);
    try {
      const rs = await api.compare(query, 100, k);
      setCompare(rs);
      toast.success("Perbandingan engine selesai");
    } catch (e: any) {
      toast.error("Gagal membandingkan", { description: String(e.message || e) });
    } finally {
      setCompareLoading(false);
    }
  }

  const fastest = compare?.reduce<BenchResp | null>(
    (best, r) => (best === null || r.p50_ms < best.p50_ms ? r : best), null);

  return (
    <TooltipProvider delayDuration={200}>
      <div className="min-h-screen bg-gradient-to-b from-background via-background to-muted/30">
        <div className="mx-auto max-w-6xl px-4 py-6">
          {/* Header */}
          <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <h1 className="text-xl font-bold tracking-tight">SIKA</h1>
                <p className="text-xs text-muted-foreground">
                  Asisten Kepatuhan Internal · Exact k-NN (HPC)
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {status && (
                <>
                  <Badge variant="muted" className="gap-1"><BookOpen className="h-3 w-3" /> {status.corpus ?? status.source}</Badge>
                  <Badge variant="muted" className="gap-1">N={fmt(status.n, 0)} · D={status.dim}</Badge>
                  <Badge variant="secondary" className="gap-1 font-mono">{status.llm.model}</Badge>
                </>
              )}
              <Tooltip><TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => setDark(!dark)}>
                  {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>
              </TooltipTrigger><TooltipContent>Tema terang/gelap</TooltipContent></Tooltip>
              <Button variant="outline" size="sm" onClick={() => setShowSettings(true)}>
                <Settings className="h-4 w-4" /> Provider
              </Button>
            </div>
          </header>

          {/* Engine + controls */}
          <Card className="mb-4">
            <CardContent className="flex flex-wrap items-center gap-2 py-3">
              <span className="mr-1 text-sm text-muted-foreground">Engine aktif:</span>
              {engines.map((e) => (
                <Button key={e} size="sm" variant={e === engine ? "success" : "outline"}
                  onClick={() => onSwapEngine(e)} className="gap-1.5">
                  {ENGINE_ICON[e]} {e}
                </Button>
              ))}
              <div className="ml-auto flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <Label htmlFor="k" className="text-xs text-muted-foreground">k</Label>
                  <Input id="k" type="number" min={1} max={100} value={k}
                    onChange={(e) => setK(parseInt(e.target.value || "10"))} className="h-8 w-16" />
                </div>
                <div className="flex items-center gap-2">
                  <Switch id="llm" checked={useLlm} onCheckedChange={setUseLlm} />
                  <Label htmlFor="llm" className="text-xs text-muted-foreground">LLM</Label>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Query bar */}
          <Card className="mb-4">
            <CardContent className="flex flex-wrap items-center gap-2 py-3">
              <div className="relative flex-1 min-w-[260px]">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="h-10 pl-9" placeholder="Tanyakan sesuatu tentang SOP/kepatuhan…"
                  value={query} onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && onAsk()} />
              </div>
              <Button onClick={onAsk} disabled={loading} className="h-10">
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />} Tanya
              </Button>
              <Button onClick={onBench} disabled={benchLoading} variant="secondary" className="h-10">
                {benchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="h-4 w-4" />} Bench 100×
              </Button>
              <Button onClick={onCompare} disabled={compareLoading} variant="outline" className="h-10">
                {compareLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <BarChart3 className="h-4 w-4" />} Bandingkan
              </Button>
            </CardContent>
          </Card>

          {/* Results grid */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-primary" /> Jawaban
                </CardTitle>
              </CardHeader>
              <CardContent>
                {!answer && !loading && (
                  <p className="text-sm text-muted-foreground">Ajukan pertanyaan untuk melihat jawaban beserta kutipan pasal.</p>
                )}
                {loading && (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-3/4" /><Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-5/6" /><Skeleton className="h-20 w-full" />
                  </div>
                )}
                {answer && (
                  <>
                    <div className="rounded-lg border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">
                      {answer.answer}
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground font-mono">status LLM: {answer.llm_status}</div>
                    <Tabs defaultValue="citations" className="mt-4">
                      <TabsList>
                        <TabsTrigger value="citations">Kutipan pasal</TabsTrigger>
                        <TabsTrigger value="latency">Latensi</TabsTrigger>
                      </TabsList>
                      <TabsContent value="citations"><CitationList items={answer.citations} /></TabsContent>
                      <TabsContent value="latency"><LatencyTable a={answer} /></TabsContent>
                    </Tabs>
                  </>
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4 text-primary" /> Telemetri
                  </CardTitle>
                  <CardDescription>Latensi per tahap</CardDescription>
                </CardHeader>
                <CardContent>
                  {answer ? <LatencyTable a={answer} /> : <p className="text-sm text-muted-foreground">Belum ada data.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Gauge className="h-4 w-4 text-primary" /> Beban 100 query
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {bench ? <BenchTable b={bench} /> : <p className="text-sm text-muted-foreground">Klik “Bench 100×”.</p>}
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Compare section */}
          {(compare || compareLoading) && (
            <Card className="mt-4">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-4 w-4 text-primary" /> Perbandingan Engine
                  {fastest && (
                    <Badge variant="success" className="ml-2 gap-1">
                      <Trophy className="h-3 w-3" /> tercepat: {fastest.engine}
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>p50 / p95 (ms) dan QPS, 100 query x 3 ulangan per engine (median, dengan warmup)</CardDescription>
              </CardHeader>
              <CardContent>
                {compareLoading && <div className="space-y-2"><Skeleton className="h-40 w-full" /><Skeleton className="h-4 w-1/2" /></div>}
                {compare && <CompareView data={compare} />}
              </CardContent>
            </Card>
          )}

          <footer className="mt-8 text-center text-xs text-muted-foreground">
            SIKA · Exact k-NN (HPC) · baseline · openmp · cuda
          </footer>
        </div>

        <ProviderDialog open={showSettings} onOpenChange={setShowSettings}
          initial={status?.llm} onSaved={() => { setShowSettings(false); refreshStatus(); }} />
      </div>
    </TooltipProvider>
  );
}

function CitationList({ items }: { items: Neighbor[] }) {
  return (
    <ScrollArea className="max-h-[420px] pr-3">
      <ol className="space-y-3">
        {items.map((c) => (
          <li key={c.rank} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="success" className="font-mono">{c.meta.sop} {c.meta.pasal}</Badge>
              <span className="text-xs text-muted-foreground">
                {c.meta.judul} · {c.meta.tahun} · {c.meta.unit}
              </span>
              <Badge variant="outline" className="ml-auto font-mono">d={c.distance.toFixed(4)}</Badge>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-foreground/90">{c.text}</p>
          </li>
        ))}
      </ol>
    </ScrollArea>
  );
}

function LatencyTable({ a }: { a: AskResp }) {
  const rows = [
    ["Embedding", a.latency.embed_ms],
    [`Retrieval (${a.engine})`, a.latency.retrieval_ms],
    ["LLM", a.latency.llm_ms],
    ["Total", a.latency.total_ms],
  ] as const;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Sumber hasil:</span>
        {a.cached ? (
          <Badge variant="success">dari cache</Badge>
        ) : (
          <Badge variant="outline">hitung baru</Badge>
        )}
      </div>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <tbody>
            {rows.map(([label, val], i) => (
              <tr key={label} className={i < rows.length - 1 ? "border-b" : ""}>
                <td className="px-3 py-2 text-muted-foreground">{label}</td>
                <td className="px-3 py-2 text-right font-mono">{fmt(val as number)} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BenchTable({ b }: { b: BenchResp }) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full text-sm">
        <tbody>
          {[
            ["Engine", b.engine],
            ["p50", `${fmt(b.p50_ms)} ms`],
            ["p95", `${fmt(b.p95_ms)} ms`],
            ["p99", `${fmt(b.p99_ms)} ms`],
            ["QPS", fmt(b.qps, 1)],
            ...(b.std_ms != null ? [["std latensi", `${fmt(b.std_ms)} ms`] as [string, string]] : []),
            ...(b.qps_cov != null ? [["variasi QPS", `±${fmt(b.qps_cov * 100, 1)}%`] as [string, string]] : []),
          ].map(([l, v], i, arr) => (
            <tr key={l} className={i < arr.length - 1 ? "border-b" : ""}>
              <td className="px-3 py-2 text-muted-foreground">{l}</td>
              <td className="px-3 py-2 text-right font-mono">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompareView({ data }: { data: BenchResp[] }) {
  const chartData = data.map((r) => ({ engine: r.engine, p50: r.p50_ms, p95: r.p95_ms, qps: r.qps }));
  const axis = { fontSize: 12, fill: "hsl(var(--muted-foreground))" } as const;
  const tooltipStyle = {
    background: "hsl(var(--popover))",
    border: "1px solid hsl(var(--border))",
    borderRadius: 8,
    fontSize: 12,
    color: "hsl(var(--popover-foreground))",
  };
  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Latensi (ms), lebih kecil lebih baik</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="engine" tick={axis} axisLine={false} tickLine={false} />
              <YAxis tick={axis} axisLine={false} tickLine={false} />
              <RTooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="p50" name="p50" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="p95" name="p95" fill="hsl(var(--success))" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">Throughput (QPS), lebih besar lebih baik</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis dataKey="engine" tick={axis} axisLine={false} tickLine={false} />
              <YAxis tick={axis} axisLine={false} tickLine={false} />
              <RTooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }} />
              <Bar dataKey="qps" name="QPS" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {chartData.map((d) => (
                  <Cell key={d.engine} fill={ENGINE_COLOR[d.engine] ?? "hsl(var(--primary))"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Engine</TableHead>
              <TableHead className="text-right">p50 (ms)</TableHead>
              <TableHead className="text-right">p95 (ms)</TableHead>
              <TableHead className="text-right">p99 (ms)</TableHead>
              <TableHead className="text-right">QPS</TableHead>
              <TableHead className="text-right">QPS variasi</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((r) => (
              <TableRow key={r.engine}>
                <TableCell>
                  <Badge variant="outline" className="gap-1">{ENGINE_ICON[r.engine]} {r.engine}</Badge>
                </TableCell>
                <TableCell className="text-right font-mono">{fmt(r.p50_ms, 3)}</TableCell>
                <TableCell className="text-right font-mono">{fmt(r.p95_ms, 3)}</TableCell>
                <TableCell className="text-right font-mono">{fmt(r.p99_ms, 3)}</TableCell>
                <TableCell className="text-right font-mono">{fmt(r.qps, 1)}</TableCell>
                <TableCell className="text-right font-mono">
                  {r.qps_cov != null ? `±${fmt((r.qps_cov ?? 0) * 100, 1)}%` : "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function ProviderDialog({
  open, onOpenChange, initial, onSaved,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: { base_url: string; model: string; api_key: string };
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

  useEffect(() => {
    if (!open) return;
    api.getConfig().then((c) => setCfg((p) => ({ ...p, ...c, api_key: "" }))).catch(() => {});
  }, [open]);

  async function fetchModels() {
    setBusy(true);
    try {
      if (cfg.api_key || cfg.base_url)
        await api.setConfig({ base_url: cfg.base_url, api_key: cfg.api_key });
      const r = await api.models();
      setModels(r.models);
      toast.success(`${r.models.length} model ditemukan`);
    } catch (e: any) {
      toast.error("Gagal fetch model", { description: String(e.message || e) });
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    try {
      const patch: Partial<LLMConfig> = {
        base_url: cfg.base_url, model: cfg.model,
        max_tokens: cfg.max_tokens, timeout_s: cfg.timeout_s,
      };
      if (cfg.api_key) patch.api_key = cfg.api_key;
      await api.setConfig(patch);
      toast.success("Konfigurasi provider disimpan");
      onSaved();
    } catch (e: any) {
      toast.error("Gagal simpan", { description: String(e.message || e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Provider LLM</DialogTitle>
          <DialogDescription>
            Koneksi OpenAI-compatible. Ganti base URL, API key, dan model kapan saja.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="base">Base URL</Label>
            <Input id="base" value={cfg.base_url}
              onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="key">API Key</Label>
            <Input id="key" type="password" placeholder="(kosongkan untuk mempertahankan)"
              value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label>Model</Label>
            <div className="flex gap-2">
              <Button variant="outline" onClick={fetchModels} disabled={busy} className="shrink-0">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Fetch
              </Button>
              {models.length > 0 ? (
                <Select value={cfg.model} onValueChange={(v) => setCfg({ ...cfg, model: v })}>
                  <SelectTrigger><SelectValue placeholder="Pilih model" /></SelectTrigger>
                  <SelectContent>
                    {models.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : (
                <Input placeholder="model id" value={cfg.model}
                  onChange={(e) => setCfg({ ...cfg, model: e.target.value })} />
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="mt">max_tokens</Label>
              <Input id="mt" type="number" value={cfg.max_tokens}
                onChange={(e) => setCfg({ ...cfg, max_tokens: parseInt(e.target.value || "512") })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to">timeout (s)</Label>
              <Input id="to" type="number" value={cfg.timeout_s}
                onChange={(e) => setCfg({ ...cfg, timeout_s: parseFloat(e.target.value || "60") })} />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button onClick={save} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Simpan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
