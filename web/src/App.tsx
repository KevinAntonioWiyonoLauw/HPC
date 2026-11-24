import { useEffect, useRef, useState } from "react";
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, BookOpen, Check, Copy,
  Cpu, Database, FileText, FolderOpen, Gauge, History, LayoutDashboard,
  Layers, ListChecks, Loader2, Menu, Moon, PanelLeftClose, PanelLeftOpen,
  RefreshCw, Search, Settings, Square, Star, Sun, Trash2, Trophy, Upload,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine,
  ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis,
} from "recharts";

import {
  api, AskResp, BenchResp, DocItem, LLMConfig, Neighbor, Status,
} from "./api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Sheet, SheetContent, SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";

// ---------------------------------------------------------------------------
// util
// ---------------------------------------------------------------------------
function fmt(n: number, d = 2) {
  return (n ?? 0).toLocaleString("id-ID", { maximumFractionDigits: d });
}
function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const ENGINE_LABEL: Record<string, string> = {
  baseline: "Baseline", openmp: "OpenMP", cuda: "CUDA", mpi: "MPI",
};
// Satu warna per engine, diturunkan dari aksen + netral (bukan pelangi).
const ENGINE_COLOR: Record<string, string> = {
  baseline: "hsl(200 10% 55%)",
  openmp: "hsl(174 62% 32%)",
  cuda: "hsl(152 55% 34%)",
  mpi: "hsl(32 70% 45%)",
};

const EXAMPLE_QUESTIONS = [
  "Apakah pembelian lisensi perangkat lunak senilai 40 juta memerlukan dua penawaran pembanding?",
  "Berapa uang harian perjalanan dinas luar kota?",
  "Apakah data pribadi boleh dikirim ke layanan AI publik di luar organisasi?",
  "Berapa batas waktu pengajuan reimbursement?",
  "Apa yang harus dilakukan jika terjadi insiden kebocoran data pribadi?",
];

const LS_FAVORITES = "sika:favorites";
const LS_HISTORY = "sika:history";

type HistPoint = {
  t: number; engine: string; retr: number; total: number; cached: boolean; swap?: boolean;
};
function loadFavorites(): Set<string> {
  try { const raw = localStorage.getItem(LS_FAVORITES); if (raw) return new Set(JSON.parse(raw)); } catch {}
  return new Set();
}
function saveFavorites(s: Set<string>) { try { localStorage.setItem(LS_FAVORITES, JSON.stringify([...s])); } catch {} }
function loadHistory(): HistPoint[] {
  try { const raw = localStorage.getItem(LS_HISTORY); if (raw) return (JSON.parse(raw) as HistPoint[]).slice(-50); } catch {}
  return [];
}
function saveHistory(h: HistPoint[]) { try { localStorage.setItem(LS_HISTORY, JSON.stringify(h.slice(-50))); } catch {} }
function favKey(n: Neighbor) { return `${n.meta.sop ?? ""} ${n.meta.pasal ?? ""}`.trim() || `idx-${n.index}`; }

type PageKey = "ask" | "benchmark" | "documents" | "overview" | "settings";

const NAV: { key: PageKey; label: string; icon: React.ReactNode; hint: string }[] = [
  { key: "ask", label: "Tanya", icon: <Search className="h-4 w-4" />, hint: "Ajukan pertanyaan kepatuhan" },
  { key: "benchmark", label: "Benchmark", icon: <BarChart3 className="h-4 w-4" />, hint: "Bandingkan kecepatan engine" },
  { key: "documents", label: "Dokumen", icon: <FolderOpen className="h-4 w-4" />, hint: "Kelola berkas regulasi" },
  { key: "overview", label: "Ikhtisar", icon: <LayoutDashboard className="h-4 w-4" />, hint: "Status sistem" },
  { key: "settings", label: "Pengaturan", icon: <Settings className="h-4 w-4" />, hint: "Provider LLM" },
];

// ---------------------------------------------------------------------------
// App shell
// ---------------------------------------------------------------------------
export default function App() {
  const [page, setPage] = useState<PageKey>("ask");
  const [navOpen, setNavOpen] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [dark, setDark] = useState(false);
  const [showProvider, setShowProvider] = useState(false);
  const [engine, setEngine] = useState("baseline");
  const [engines, setEngines] = useState<string[]>([]);
  // Sidebar bisa dibuka/tutup di desktop (rail ikon vs lebar penuh), diingat antar sesi.
  // Bisa juga diatur awal via ?nav=collapsed|expanded (deep-link).
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    const q = new URLSearchParams(window.location.search).get("nav");
    if (q === "collapsed") return true;
    if (q === "expanded") return false;
    try { return localStorage.getItem("sika:nav-collapsed") === "1"; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem("sika:nav-collapsed", collapsed ? "1" : "0"); } catch {}
  }, [collapsed]);

  async function refreshStatus() {
    try {
      const s = await api.status();
      setStatus(s); setEngine(s.engine_active); setEngines(s.engines);
    } catch (e: any) {
      toast.error("Gagal memuat status", { description: String(e.message || e) });
    }
  }
  useEffect(() => { refreshStatus(); }, []);
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); }, [dark]);
  // Rute ringan via ?page= agar tiap layar punya URL sendiri (bisa di-bookmark/di-reload).
  const PAGES: PageKey[] = ["ask", "benchmark", "documents", "overview", "settings"];
  function go(p: PageKey) {
    setPage(p);
    const url = new URL(window.location.href);
    url.searchParams.set("page", p);
    window.history.pushState({ page: p }, "", url);
  }
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("page");
    if (p && PAGES.includes(p as PageKey)) setPage(p as PageKey);
    const onPop = () => {
      const q = new URLSearchParams(window.location.search).get("page");
      if (q && PAGES.includes(q as PageKey)) setPage(q as PageKey);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  return (
    <TooltipProvider delayDuration={200}>
      <div
        className={cn(
          "min-h-screen bg-background text-foreground md:grid md:transition-[grid-template-columns] md:duration-200",
          collapsed ? "md:grid-cols-[72px_1fr]" : "md:grid-cols-[256px_1fr]"
        )}
      >
        {/* Sidebar desktop: rail ikon (72px) atau lebar penuh (256px) */}
        <aside
          className={cn(
            "hidden flex-col overflow-hidden border-r border-border bg-card transition-[width] duration-200 md:static md:flex",
            collapsed ? "md:w-[72px]" : "md:w-[256px]"
          )}
        >
          <div className={cn("flex items-center py-4", collapsed ? "justify-center px-2" : "gap-2.5 px-4")}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <FileText className="h-5 w-5" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <div className="font-serif text-lg font-semibold leading-none tracking-tight">SIKA</div>
                <div className="mt-1 truncate text-[11px] text-muted-foreground">Konsol Kepatuhan Internal</div>
              </div>
            )}
          </div>
          <Separator />

          <nav className={cn("flex flex-1 flex-col gap-1 py-3", collapsed ? "items-center px-2" : "px-3")} aria-label="Navigasi utama">
            {NAV.map((n) => {
              const active = page === n.key;
              if (collapsed) {
                return (
                  <Tooltip key={n.key}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => go(n.key)}
                        aria-current={active ? "page" : undefined}
                        aria-label={n.label}
                        className="nav-item h-10 w-10 justify-center px-0"
                        data-active={active}
                      >
                        {n.icon}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="right">{n.label}</TooltipContent>
                  </Tooltip>
                );
              }
              return (
                <button
                  key={n.key}
                  onClick={() => go(n.key)}
                  aria-current={active ? "page" : undefined}
                  className="nav-item w-full"
                  data-active={active}
                >
                  {n.icon}
                  <span>{n.label}</span>
                </button>
              );
            })}
          </nav>

          <Separator />
          <div className={cn("py-3", collapsed ? "px-2" : "px-3")}>
            {!collapsed && (
              <div className="mb-2 space-y-1 px-1 text-[11px] text-muted-foreground">
                {status ? (
                  <>
                    <div className="flex items-center gap-1.5"><Database className="h-3 w-3" /> {status.corpus ?? status.source}</div>
                    <div className="tabular-nums">N={fmt(status.n, 0)} · D={status.dim}</div>
                    <div className="flex items-center gap-1.5"><Cpu className="h-3 w-3" /> engine: {ENGINE_LABEL[engine] ?? engine}</div>
                  </>
                ) : "memuat status…"}
              </div>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setCollapsed((c) => !c)}
                  aria-label={collapsed ? "Lebarkan sidebar" : "Sempitkan sidebar"}
                  aria-pressed={collapsed}
                  className={cn("nav-item", collapsed ? "h-10 w-10 justify-center px-0" : "w-full")}
                >
                  {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
                  {!collapsed && <span>Sempitkan</span>}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{collapsed ? "Lebarkan sidebar" : "Sempitkan sidebar"}</TooltipContent>
            </Tooltip>
          </div>
        </aside>

        {/* Sidebar mobile: drawer (Radix Sheet) dengan overlay */}
        <Sheet open={navOpen} onOpenChange={setNavOpen}>
          <SheetContent side="left" className="flex w-[280px] flex-col p-0 sm:max-w-[280px]">
            <SheetTitle className="sr-only">Navigasi</SheetTitle>
            <div className="flex items-center gap-2.5 px-4 py-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
                <FileText className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="font-serif text-lg font-semibold leading-none tracking-tight">SIKA</div>
                <div className="mt-1 truncate text-[11px] text-muted-foreground">Konsol Kepatuhan Internal</div>
              </div>
            </div>
            <Separator />
            <nav className="flex flex-1 flex-col gap-1 px-3 py-3" aria-label="Navigasi utama">
              {NAV.map((n) => {
                const active = page === n.key;
                return (
                  <button
                    key={n.key}
                    onClick={() => { go(n.key); setNavOpen(false); }}
                    aria-current={active ? "page" : undefined}
                    className="nav-item w-full"
                    data-active={active}
                  >
                    {n.icon}
                    <span>{n.label}</span>
                  </button>
                );
              })}
            </nav>
            <Separator />
            <div className="px-4 py-3 text-[11px] text-muted-foreground">
              {status ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5"><Database className="h-3 w-3" /> {status.corpus ?? status.source}</div>
                  <div className="tabular-nums">N={fmt(status.n, 0)} · D={status.dim}</div>
                  <div className="flex items-center gap-1.5"><Cpu className="h-3 w-3" /> engine: {ENGINE_LABEL[engine] ?? engine}</div>
                </div>
              ) : "memuat status…"}
            </div>
          </SheetContent>
        </Sheet>

        {/* Main */}
        <div className="flex min-w-0 flex-col">
          <header className="flex items-center gap-3 border-b border-border bg-card/60 px-4 py-3 md:px-8">
            <button className="rounded-md p-1.5 text-muted-foreground hover:bg-muted md:hidden" onClick={() => setNavOpen(true)} aria-label="Buka menu">
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate font-serif text-lg font-semibold">{NAV.find((n) => n.key === page)?.label}</h1>
              <p className="truncate text-xs text-muted-foreground">{NAV.find((n) => n.key === page)?.hint}</p>
            </div>
            <div className="ml-auto flex items-center gap-2">
              {status && <Badge variant="muted" className="hidden font-mono sm:inline-flex">{status.llm.model}</Badge>}
              <Tooltip><TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={() => setDark(!dark)} aria-label="Ganti tema">
                  {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
                </Button>
              </TooltipTrigger><TooltipContent>Ganti tema</TooltipContent></Tooltip>
              <Button variant="outline" size="sm" onClick={() => setShowProvider(true)}>
                <Settings className="h-4 w-4" /> Provider
              </Button>
            </div>
          </header>

          <main className="flex-1 px-4 py-6 md:px-8">
            {page === "ask" && <AskPage status={status} engine={engine} engines={engines} setEngine={setEngine} refreshStatus={refreshStatus} />}
            {page === "benchmark" && <BenchmarkPage status={status} engine={engine} engines={engines} />}
            {page === "documents" && <DocumentsPage status={status} onCorpusChanged={refreshStatus} />}
            {page === "overview" && <OverviewPage status={status} engines={engines} engine={engine} />}
            {page === "settings" && <SettingsPage status={status} refreshStatus={refreshStatus} onOpenProvider={() => setShowProvider(true)} />}
          </main>
        </div>

        <ProviderDialog open={showProvider} onOpenChange={setShowProvider}
          initial={status?.llm} onSaved={() => { setShowProvider(false); refreshStatus(); }} />
      </div>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// shared bits
// ---------------------------------------------------------------------------
function SectionTitle({ icon, title, desc, right }: { icon: React.ReactNode; title: string; desc?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="flex items-center gap-2">
        <span className="text-primary">{icon}</span>
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {desc && <p className="text-xs text-muted-foreground">{desc}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

function EmptyState({ icon, title, desc, action }: { icon: React.ReactNode; title: string; desc: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border px-6 py-12 text-center">
      <div className="text-muted-foreground">{icon}</div>
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-sm text-xs text-muted-foreground">{desc}</p>
      {action}
    </div>
  );
}

function EnginePills({ engines, engine, onPick }: { engines: string[]; engine: string; onPick: (e: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="group" aria-label="Pilih engine">
      {engines.map((e) => (
        <button key={e} onClick={() => onPick(e)} aria-pressed={e === engine}
          className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
            e === engine
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground"
          }`}>
          {ENGINE_LABEL[e] ?? e}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ask page
// ---------------------------------------------------------------------------
function AskPage({ status, engine, engines, setEngine, refreshStatus }: {
  status: Status | null; engine: string; engines: string[];
  setEngine: (e: string) => void; refreshStatus: () => void;
}) {
  const [query, setQuery] = useState("Apakah pembelian lisensi perangkat lunak senilai 40 juta memerlukan dua penawaran pembanding?");
  const [k, setK] = useState(10);
  const [useLlm, setUseLlm] = useState(true);
  const [answer, setAnswer] = useState<AskResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [streamCitations, setStreamCitations] = useState<Neighbor[] | null>(null);
  const [streamStatus, setStreamStatus] = useState("");
  const abortRef = useRef<null | (() => void)>(null);
  const [history, setHistory] = useState<HistPoint[]>(() => loadHistory());
  const [favorites, setFavorites] = useState<Set<string>>(() => loadFavorites());

  function pushHistory(p: Omit<HistPoint, "t">) {
    setHistory((prev) => {
      const next = [...prev, { ...p, t: (prev.length ? prev[prev.length - 1].t : 0) + 1 }].slice(-50);
      saveHistory(next); return next;
    });
  }
  function clearHistory() { setHistory([]); saveHistory([]); toast.success("Riwayat dihapus"); }
  function toggleFavorite(n: Neighbor) {
    setFavorites((prev) => { const nx = new Set(prev); const key = favKey(n); nx.has(key) ? nx.delete(key) : nx.add(key); saveFavorites(nx); return nx; });
  }
  async function copyRef(n: Neighbor) {
    const ref = `${n.meta.sop ?? ""} ${n.meta.pasal ?? ""}`.trim();
    try { await navigator.clipboard.writeText(ref); toast.success(`Disalin: ${ref}`); }
    catch { toast.error("Gagal menyalin"); }
  }
  async function onSwap(name: string) {
    try { const r = await api.setEngine(name); setEngine(r.active); refreshStatus(); pushHistory({ engine: r.active, retr: 0, total: 0, cached: false, swap: true }); }
    catch (e: any) { toast.error("Gagal tukar engine", { description: String(e.message || e) }); }
  }
  function onStream() {
    if (!query.trim() || streaming) return;
    setStreaming(true); setStreamText(""); setStreamCitations(null); setStreamStatus(""); setAnswer(null);
    const started = performance.now();
    abortRef.current = api.askStream(query, k, useLlm, (e) => {
      if (e.type === "citations") setStreamCitations(e.citations);
      else if (e.type === "delta") setStreamText((t) => t + e.text);
      else if (e.type === "done") { setStreamStatus(e.llm_status); setStreaming(false); pushHistory({ engine, retr: e.llm_ms ?? 0, total: e.total_ms ?? performance.now() - started, cached: false }); }
    });
  }
  function stopStream() { abortRef.current?.(); abortRef.current = null; setStreaming(false); setStreamStatus((s) => s || "dihentikan pengguna"); }
  async function onAsk() {
    if (!query.trim()) return;
    setLoading(true); setAnswer(null);
    try { const a = await api.ask(query, k, useLlm); setAnswer(a); pushHistory({ engine: a.engine, retr: a.latency.retrieval_ms, total: a.latency.total_ms, cached: a.cached }); }
    catch (e: any) { toast.error("Permintaan gagal", { description: String(e.message || e) }); }
    finally { setLoading(false); }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      {/* Query console */}
      <section className="panel p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <EnginePills engines={engines} engine={engine} onPick={onSwap} />
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="k" className="text-xs text-muted-foreground">k</Label>
              <Input id="k" type="number" min={1} max={100} value={k}
                onChange={(e) => setK(parseInt(e.target.value || "10"))} className="h-8 w-16" />
            </div>
            <div className="flex items-center gap-1.5">
              <Switch id="llm" checked={useLlm} onCheckedChange={setUseLlm} />
              <Label htmlFor="llm" className="text-xs text-muted-foreground">LLM</Label>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-11 pl-9" placeholder="Tanyakan sesuatu tentang SOP / regulasi kepatuhan…"
              value={query} onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onAsk()} />
          </div>
          <div className="flex gap-2">
            <Button onClick={onAsk} disabled={loading || streaming} className="h-11">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />} Tanya
            </Button>
            <Button onClick={streaming ? stopStream : onStream} disabled={loading}
              variant={streaming ? "destructive" : "secondary"} className="h-11">
              {streaming ? <><Square className="h-4 w-4" /> Stop</> : <><Activity className="h-4 w-4" /> Stream</>}
            </Button>
          </div>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground"><ListChecks className="h-3.5 w-3.5" /> Contoh:</span>
          {EXAMPLE_QUESTIONS.map((q) => (
            <button key={q} onClick={() => setQuery(q)}
              className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
              {q.length > 44 ? q.slice(0, 44) + "…" : q}
            </button>
          ))}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Answer */}
        <section className="panel lg:col-span-2">
          <div className="border-b border-border px-4 py-3">
            <SectionTitle icon={<FileText className="h-4 w-4" />} title="Jawaban" desc="Bersumber hanya dari kutipan pasal yang ditemukan" />
          </div>
          <div className="p-4">
            {!answer && !loading && !streaming && !streamText && !streamCitations && (
              <EmptyState icon={<FileText className="h-6 w-6" />} title="Belum ada jawaban"
                desc="Ajukan pertanyaan di atas. Jawaban akan disertai kutipan pasal asli yang dapat disalin." />
            )}
            {loading && <div className="space-y-2"><Skeleton className="h-4 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-20 w-full" /></div>}

            {(streaming || streamText || streamCitations) && (
              <>
                {streamCitations && (
                  <div className="mb-3">
                    <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="success">kutipan lebih dulu</Badge>
                      <span>{streamCitations.length} pasal</span>
                    </div>
                    <CitationList items={streamCitations} favorites={favorites} onCopy={copyRef} onToggleFav={toggleFavorite} />
                  </div>
                )}
                <div className="rounded-md border border-border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">
                  {streamText || (streaming ? "…" : "")}
                  {streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" />}
                </div>
                <div className="mt-2 text-xs text-muted-foreground">status LLM: {streamStatus || (streaming ? "streaming…" : "")}</div>
              </>
            )}

            {answer && (
              <>
                <div className="rounded-md border border-border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">{answer.answer}</div>
                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>status LLM: {answer.llm_status}</span>
                  {answer.cached ? <Badge variant="success">dari cache</Badge> : <Badge variant="outline">hitung baru</Badge>}
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Kutipan pasal</h3>
                    <CitationList items={answer.citations} favorites={favorites} onCopy={copyRef} onToggleFav={toggleFavorite} />
                  </div>
                  <div>
                    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Latensi per tahap</h3>
                    <LatencyTable a={answer} />
                  </div>
                </div>
              </>
            )}
          </div>
        </section>

        {/* Right rail */}
        <div className="space-y-4">
          <section className="panel">
            <div className="border-b border-border px-4 py-3">
              <SectionTitle icon={<History className="h-4 w-4" />} title="Riwayat" desc="Latensi & QPS per permintaan"
                right={<Button variant="ghost" size="sm" onClick={clearHistory} disabled={history.length === 0} className="gap-1 text-xs"><Trash2 className="h-3.5 w-3.5" /> Hapus</Button>} />
            </div>
            <div className="p-4"><HistorySparkline points={history} /></div>
          </section>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Benchmark page
// ---------------------------------------------------------------------------
function BenchmarkPage({ status, engine, engines }: { status: Status | null; engine: string; engines: string[] }) {
  const [query, setQuery] = useState("pengadaan perangkat lunak lisensi");
  const [k, setK] = useState(10);
  const [compare, setCompare] = useState<BenchResp[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    if (!query.trim()) return;
    setLoading(true); setCompare(null);
    try { setCompare(await api.compare(query, 100, k)); }
    catch (e: any) { toast.error("Gagal benchmark", { description: String(e.message || e) }); }
    finally { setLoading(false); }
  }
  const fastest = compare?.reduce<BenchResp | null>((best, r) => (best === null || r.p50_ms < best.p50_ms ? r : best), null);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <section className="panel p-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="h-11 pl-9" placeholder="Kueri uji untuk benchmark…" value={query}
              onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="bk" className="text-xs text-muted-foreground">k</Label>
              <Input id="bk" type="number" min={1} max={100} value={k} onChange={(e) => setK(parseInt(e.target.value || "10"))} className="h-9 w-16" />
            </div>
            <Button onClick={run} disabled={loading} className="h-11">
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Gauge className="h-4 w-4" />} Jalankan perbandingan
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {engines.length} engine terdeteksi: {engines.map((e) => ENGINE_LABEL[e] ?? e).join(", ")}. Tiap engine diberi pemanasan + 3 ulangan (median) agar angka stabil.
        </p>
      </section>

      <section className="panel">
        <div className="border-b border-border px-4 py-3">
          <SectionTitle icon={<BarChart3 className="h-4 w-4" />} title="Perbandingan engine" desc="100 kueri x 3 ulangan per engine"
            right={fastest && <Badge variant="success" className="gap-1"><Trophy className="h-3 w-3" /> tercepat: {ENGINE_LABEL[fastest.engine] ?? fastest.engine}</Badge>} />
        </div>
        <div className="p-4">
          {!compare && !loading && (
            <EmptyState icon={<Gauge className="h-6 w-6" />} title="Belum ada hasil"
              desc="Klik “Jalankan perbandingan” untuk mengukur p50/p95 dan QPS tiap engine pada kueri ini." />
          )}
          {loading && <div className="space-y-2"><Skeleton className="h-40 w-full" /><Skeleton className="h-4 w-1/2" /></div>}
          {compare && <CompareView data={compare} />}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Documents page
// ---------------------------------------------------------------------------
function DocumentsPage({ status, onCorpusChanged }: { status: Status | null; onCorpusChanged: () => void }) {
  const [docs, setDocs] = useState<DocItem[] | null>(null);
  const [dir, setDir] = useState("");
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [reindexing, setReindexing] = useState(false);

  async function refresh() {
    setLoading(true);
    try { const r = await api.documents(); setDocs(r.documents); setDir(r.dir); }
    catch (e: any) { toast.error("Gagal memuat dokumen", { description: String(e.message || e) }); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  async function del(name: string) {
    try { await api.deleteDocument(name); toast.success(`Dihapus: ${name}`); refresh(); }
    catch (e: any) { toast.error("Gagal menghapus", { description: String(e.message || e) }); }
  }
  async function reindex() {
    setReindexing(true);
    try {
      await api.reindexDocuments();
      toast.success("Reindex dimulai", { description: "Korpus dibangun ulang di latar belakang." });
      // poll status
      const t = setInterval(async () => {
        try {
          const s = await api.reindexStatus();
          if (!s.running) {
            clearInterval(t); setReindexing(false);
            if (s.last?.ok) { toast.success("Reindex selesai"); onCorpusChanged(); refresh(); }
            else toast.error("Reindex gagal", { description: s.last?.tail?.slice(-160) });
          }
        } catch { clearInterval(t); setReindexing(false); }
      }, 2500);
    } catch (e: any) {
      setReindexing(false);
      toast.error("Gagal memulai reindex", { description: String(e.message || e) });
    }
  }

  const totalPasal = docs?.reduce((s, d) => s + d.pasal, 0) ?? 0;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <section className="panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-primary"><FolderOpen className="h-5 w-5" /></span>
            <div>
              <h2 className="text-sm font-semibold">Berkas dokumen</h2>
              <p className="text-xs text-muted-foreground">
                {docs ? `${docs.length} berkas · ${fmt(totalPasal, 0)} pasal · korpus aktif ${status?.corpus ?? "-"}` : "memuat…"}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={reindex} disabled={reindexing} className="gap-1.5">
              {reindexing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Reindex korpus
            </Button>
            <Button onClick={() => setShowUpload(true)} className="gap-1.5"><Upload className="h-4 w-4" /> Unggah dokumen</Button>
          </div>
        </div>
        <p className="mt-2 break-all text-[11px] text-muted-foreground">Folder: <span className="font-mono">{dir}</span></p>
      </section>

      <section className="panel">
        <div className="p-4">
          {loading && <div className="space-y-2"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div>}
          {!loading && docs && docs.length === 0 && (
            <EmptyState icon={<FolderOpen className="h-6 w-6" />} title="Belum ada berkas"
              desc="Unggah berkas regulasi (.md/.txt) untuk membangun korpus, atau jalankan fetch_jdih.py di server."
              action={<Button onClick={() => setShowUpload(true)} className="mt-2 gap-1.5"><Upload className="h-4 w-4" /> Unggah dokumen</Button>} />
          )}
          {!loading && docs && docs.length > 0 && (
            <div className="overflow-hidden rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Berkas</TableHead>
                    <TableHead>Judul</TableHead>
                    <TableHead className="text-right">Pasal</TableHead>
                    <TableHead className="text-right">Ukuran</TableHead>
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docs.map((d) => (
                    <TableRow key={d.name}>
                      <TableCell className="font-mono text-xs">{d.name}</TableCell>
                      <TableCell className="max-w-[320px] truncate" title={d.title}>{d.title}</TableCell>
                      <TableCell className="text-right tabular-nums">{d.pasal}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">{bytes(d.size)}</TableCell>
                      <TableCell>
                        <Tooltip><TooltipTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => del(d.name)} aria-label={`Hapus ${d.name}`}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </TooltipTrigger><TooltipContent>Hapus berkas</TooltipContent></Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </section>

      <UploadDialog open={showUpload} onOpenChange={setShowUpload}
        onDone={() => { setShowUpload(false); refresh(); }} />
    </div>
  );
}

function UploadDialog({ open, onOpenChange, onDone }: { open: boolean; onOpenChange: (v: boolean) => void; onDone: () => void }) {
  const [name, setName] = useState("");
  const [title, setTitle] = useState("");
  const [year, setYear] = useState("");
  const [unit, setUnit] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) { setName(""); setTitle(""); setYear(""); setUnit(""); setContent(""); }
  }, [open]);

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!name) setName(f.name);
    const reader = new FileReader();
    reader.onload = () => setContent(String(reader.result || ""));
    reader.readAsText(f);
  }

  async function save() {
    if (!content.trim()) { toast.error("Isi dokumen kosong"); return; }
    setBusy(true);
    try {
      await api.uploadDocument({ name: name || "dokumen.md", content, title, year, unit });
      toast.success("Dokumen tersimpan", { description: "Klik Reindex korpus agar ikut terindeks." });
      onDone();
    } catch (e: any) { toast.error("Gagal menyimpan", { description: String(e.message || e) }); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Unggah dokumen</DialogTitle>
          <DialogDescription>Impor berkas .md/.txt berisi pasal, atau tempel teks. Berkas disimpan di folder dokumen server.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5 sm:col-span-3">
              <Label htmlFor="fname">Nama berkas</Label>
              <Input id="fname" placeholder="uu-no-27-tahun-2022.md" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ftitle">Judul (opsional)</Label>
              <Input id="ftitle" placeholder="Pelindungan Data Pribadi" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="fyear">Tahun</Label>
              <Input id="fyear" placeholder="2022" value={year} onChange={(e) => setYear(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="funit">Unit (opsional)</Label>
              <Input id="funit" placeholder="Unit Kepatuhan" value={unit} onChange={(e) => setUnit(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" accept=".md,.txt,text/plain,text/markdown" onChange={onFile} className="hidden" />
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} className="gap-1.5"><Upload className="h-4 w-4" /> Pilih berkas</Button>
            <span className="text-xs text-muted-foreground">atau tempel teks di bawah</span>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fcontent">Isi (format pasal: “Pasal 1”, “Pasal 2”, …)</Label>
            <Textarea id="fcontent" className="min-h-[160px] font-mono text-xs" placeholder={"Pasal 1\nIsi pasal pertama…\nPasal 2\nIsi pasal kedua…"}
              value={content} onChange={(e) => setContent(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button onClick={save} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Simpan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Overview page
// ---------------------------------------------------------------------------
function OverviewPage({ status, engines, engine }: { status: Status | null; engines: string[]; engine: string }) {
  const [queue, setQueue] = useState<any>(null);
  useEffect(() => {
    fetch("/api/queue/stats").then((r) => (r.ok ? r.json() : null)).then(setQueue).catch(() => {});
  }, []);
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <section className="panel p-5">
        <SectionTitle icon={<LayoutDashboard className="h-4 w-4" />} title="Status sistem" desc="Nilai nyata dari layanan, tanpa angka contoh" />
        {!status ? <p className="text-sm text-muted-foreground">Memuat…</p> : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Korpus" value={status.corpus ?? status.source} hint={`${fmt(status.n, 0)} vektor · D=${status.dim}`} />
            <Stat label="Engine aktif" value={ENGINE_LABEL[engine] ?? engine} hint={`${engines.length} engine tersedia`} />
            <Stat label="Mode muat" value={(status as any).load_mode ?? "preload"} hint="SIKA_LOAD_MODE" />
            <Stat label="Model LLM" value={status.llm.model} hint={status.llm.base_url} mono />
          </div>
        )}
      </section>

      <section className="panel p-5">
        <SectionTitle icon={<Cpu className="h-4 w-4" />} title="Antrean & konkurensi" desc="Dari GET /queue/stats" />
        {queue ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Batas engine" value={String(queue.engine_limit ?? "-")} hint={`antrean: ${queue.engine?.queue_depth ?? 0}`} />
            <Stat label="Tunggu engine (rata2)" value={`${fmt(queue.engine?.avg_wait_ms ?? 0, 3)} ms`} hint={`${queue.engine?.total_waits ?? 0} permintaan`} />
            <Stat label="Batas embed" value={String(queue.embed_limit ?? "-")} hint={`antrean: ${queue.embed?.queue_depth ?? 0}`} />
            <Stat label="Tunggu embed (rata2)" value={`${fmt(queue.embed?.avg_wait_ms ?? 0, 3)} ms`} hint={`${queue.embed?.total_waits ?? 0} permintaan`} />
          </div>
        ) : <p className="text-sm text-muted-foreground">Metrik antrean tidak tersedia.</p>}
      </section>
    </div>
  );
}

function Stat({ label, value, hint, mono }: { label: string; value: string; hint?: string; mono?: boolean }) {
  return (
    <div className="rounded-md border border-border p-3">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={`mt-1 truncate text-base font-semibold ${mono ? "font-mono text-sm" : ""}`} title={value}>{value}</div>
      {hint && <div className="mt-0.5 truncate text-[11px] text-muted-foreground" title={hint}>{hint}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings page
// ---------------------------------------------------------------------------
function SettingsPage({ status, refreshStatus, onOpenProvider }: { status: Status | null; refreshStatus: () => void; onOpenProvider: () => void }) {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <section className="panel p-5">
        <SectionTitle icon={<Settings className="h-4 w-4" />} title="Provider LLM" desc="Koneksi OpenAI-compatible; konfigurasi tersimpan dan bertahan setelah restart" />
        {status ? (
          <div className="space-y-2 text-sm">
            <Row k="Base URL" v={status.llm.base_url} />
            <Row k="Model" v={status.llm.model} />
            <Row k="API key" v={status.llm.api_key || "(belum diisi)"} mono />
          </div>
        ) : <p className="text-sm text-muted-foreground">Memuat…</p>}
        <Button className="mt-4 gap-1.5" onClick={onOpenProvider}><Settings className="h-4 w-4" /> Ubah konfigurasi</Button>
      </section>

      <section className="panel p-5">
        <SectionTitle icon={<BookOpen className="h-4 w-4" />} title="Tentang" desc="SIKA: Exact k-NN untuk dokumen kepatuhan" />
        <p className="text-sm leading-relaxed text-muted-foreground">
          SIKA menjawab pertanyaan kepatuhan dengan pencarian <em>exact</em> k-NN (recall 100%) atas dokumen
          regulasi, lalu menyusun jawaban dari kutipan pasal asli. Engine dapat ditukar (Baseline, OpenMP, CUDA,
          MPI) tanpa memuat ulang basis. Latensi dan QPS diukur apa adanya di panel Benchmark.
        </p>
      </section>
    </div>
  );
}
function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border py-1.5 last:border-0">
      <span className="text-muted-foreground">{k}</span>
      <span className={`truncate text-right ${mono ? "font-mono text-xs" : ""}`} title={v}>{v}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// citations / charts / tables
// ---------------------------------------------------------------------------
function CitationList({ items, favorites, onCopy, onToggleFav }: {
  items: Neighbor[]; favorites: Set<string>; onCopy: (n: Neighbor) => void; onToggleFav: (n: Neighbor) => void;
}) {
  return (
    <ScrollArea className="max-h-[420px] pr-3">
      <ol className="space-y-2.5">
        {items.map((c) => {
          const key = favKey(c); const fav = favorites.has(key);
          return (
            <li key={c.rank} className="rounded-md border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="success" className="font-mono">{c.meta.sop} {c.meta.pasal}</Badge>
                <span className="text-xs text-muted-foreground">{c.meta.judul} · {c.meta.tahun} · {c.meta.unit}</span>
                <div className="ml-auto flex items-center gap-1">
                  <Tooltip><TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onCopy(c)} aria-label="Salin rujukan pasal"><Copy className="h-3.5 w-3.5" /></Button>
                  </TooltipTrigger><TooltipContent>Salin rujukan</TooltipContent></Tooltip>
                  <Tooltip><TooltipTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onToggleFav(c)} aria-pressed={fav} aria-label={fav ? "Hapus favorit" : "Tandai favorit"}>
                      <Star className={`h-3.5 w-3.5 ${fav ? "fill-warning text-warning" : ""}`} />
                    </Button>
                  </TooltipTrigger><TooltipContent>{fav ? "Hapus favorit" : "Tandai favorit"}</TooltipContent></Tooltip>
                  <Badge variant="outline" className="font-mono">d={c.distance.toFixed(4)}</Badge>
                </div>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-foreground/90">{c.text}</p>
            </li>
          );
        })}
      </ol>
    </ScrollArea>
  );
}

function HistorySparkline({ points }: { points: HistPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-muted-foreground">Belum ada riwayat. Ajukan pertanyaan atau tukar engine untuk mulai merekam.</p>;
  }
  const data = points.map((p) => ({
    t: p.t, latency: p.swap ? null : Math.round(p.total * 100) / 100,
    qps: p.swap || p.total <= 0 ? null : Math.round((1000 / p.total) * 10) / 10,
    engine: p.engine, swap: p.swap ? p.engine : null,
  }));
  const swaps = points.filter((p) => p.swap);
  const axis = { fontSize: 11, fill: "hsl(var(--muted-foreground))" } as const;
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Latensi total (ms), lebih kecil lebih baik</p>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={data} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="t" tick={axis} axisLine={false} tickLine={false} />
          <YAxis tick={axis} axisLine={false} tickLine={false} />
          <RTooltip contentStyle={{ fontSize: 12 }} />
          {swaps.map((s) => <ReferenceLine key={s.t} x={s.t} stroke="hsl(var(--primary))" strokeDasharray="4 2" />)}
          <Line type="monotone" dataKey="latency" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="text-xs text-muted-foreground">QPS, lebih besar lebih baik</p>
      <ResponsiveContainer width="100%" height={80}>
        <LineChart data={data} margin={{ top: 6, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="t" tick={axis} axisLine={false} tickLine={false} />
          <YAxis tick={axis} axisLine={false} tickLine={false} />
          <RTooltip contentStyle={{ fontSize: 12 }} />
          {swaps.map((s) => <ReferenceLine key={s.t} x={s.t} stroke="hsl(var(--success))" strokeDasharray="4 2" />)}
          <Line type="monotone" dataKey="qps" stroke="hsl(var(--success))" strokeWidth={2} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      {swaps.length > 0 && <p className="text-xs text-muted-foreground">Garis putus-putus menandai pergantian engine.</p>}
    </div>
  );
}

function LatencyTable({ a }: { a: AskResp }) {
  const rows = [
    ["Embedding", a.latency.embed_ms],
    [`Retrieval (${ENGINE_LABEL[a.engine] ?? a.engine})`, a.latency.retrieval_ms],
    ["LLM", a.latency.llm_ms],
    ["Total", a.latency.total_ms],
  ] as const;
  return (
    <div className="overflow-hidden rounded-md border border-border">
      <table className="w-full text-sm">
        <tbody>
          {rows.map(([label, val], i) => (
            <tr key={label} className={i < rows.length - 1 ? "border-b border-border" : ""}>
              <td className="px-3 py-2 text-muted-foreground">{label}</td>
              <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(val as number)} ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BenchTable({ b }: { b: BenchResp }) {
  return (
    <div className="overflow-hidden rounded-md border border-border">
      <table className="w-full text-sm">
        <tbody>
          {[
            ["Engine", ENGINE_LABEL[b.engine] ?? b.engine],
            ["p50", `${fmt(b.p50_ms)} ms`],
            ["p95", `${fmt(b.p95_ms)} ms`],
            ["p99", `${fmt(b.p99_ms)} ms`],
            ["QPS", fmt(b.qps, 1)],
          ].map(([l, v], i, arr) => (
            <tr key={l} className={i < arr.length - 1 ? "border-b border-border" : ""}>
              <td className="px-3 py-2 text-muted-foreground">{l}</td>
              <td className="px-3 py-2 text-right tabular-nums font-mono">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompareView({ data }: { data: BenchResp[] }) {
  const chartData = data.map((r) => ({ engine: ENGINE_LABEL[r.engine] ?? r.engine, p50: r.p50_ms, p95: r.p95_ms, qps: r.qps }));
  const axis = { fontSize: 12, fill: "hsl(var(--muted-foreground))" } as const;
  const tip = { background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: 6, fontSize: 12, color: "hsl(var(--popover-foreground))" };
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
              <RTooltip contentStyle={tip} cursor={{ fill: "hsl(var(--muted))", opacity: 0.5 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="p50" name="p50" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              <Bar dataKey="p95" name="p95" fill="hsl(var(--success))" radius={[3, 3, 0, 0]} isAnimationActive={false} />
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
              <RTooltip contentStyle={tip} cursor={{ fill: "hsl(var(--muted))", opacity: 0.5 }} />
              <Bar dataKey="qps" name="QPS" radius={[3, 3, 0, 0]} isAnimationActive={false}>
                {chartData.map((d, i) => <Cell key={d.engine} fill={Object.values(ENGINE_COLOR)[i % 4]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Engine</TableHead>
              <TableHead className="text-right">p50 (ms)</TableHead>
              <TableHead className="text-right">p95 (ms)</TableHead>
              <TableHead className="text-right">p99 (ms)</TableHead>
              <TableHead className="text-right">QPS</TableHead>
              <TableHead className="text-right">Variasi QPS</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((r) => (
              <TableRow key={r.engine}>
                <TableCell className="font-medium">{ENGINE_LABEL[r.engine] ?? r.engine}</TableCell>
                <TableCell className="text-right tabular-nums font-mono">{fmt(r.p50_ms, 3)}</TableCell>
                <TableCell className="text-right tabular-nums font-mono">{fmt(r.p95_ms, 3)}</TableCell>
                <TableCell className="text-right tabular-nums font-mono">{fmt(r.p99_ms, 3)}</TableCell>
                <TableCell className="text-right tabular-nums font-mono">{fmt(r.qps, 1)}</TableCell>
                <TableCell className="text-right tabular-nums font-mono">{r.qps_cov != null ? `±${fmt((r.qps_cov ?? 0) * 100, 1)}%` : "-"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Provider dialog (reused by header + settings)
// ---------------------------------------------------------------------------
function ProviderDialog({ open, onOpenChange, initial, onSaved }: {
  open: boolean; onOpenChange: (v: boolean) => void;
  initial?: { base_url: string; model: string; api_key: string }; onSaved: () => void;
}) {
  const [cfg, setCfg] = useState<LLMConfig>({ base_url: initial?.base_url ?? "http://localhost:12800/v1", model: initial?.model ?? "", api_key: "", max_tokens: 512, timeout_s: 60 });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    api.getConfig().then((c) => setCfg((p) => ({ ...p, ...c, api_key: "" }))).catch(() => {});
  }, [open]);

  async function save() {
    setBusy(true);
    try {
      const patch: Partial<LLMConfig> = { base_url: cfg.base_url, model: cfg.model, max_tokens: cfg.max_tokens, timeout_s: cfg.timeout_s };
      if (cfg.api_key) patch.api_key = cfg.api_key;
      await api.setConfig(patch);
      toast.success("Konfigurasi provider disimpan");
      onSaved();
    } catch (e: any) { toast.error("Gagal simpan", { description: String(e.message || e) }); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Provider LLM</DialogTitle>
          <DialogDescription>Koneksi OpenAI-compatible. Perubahan tersimpan dan bertahan setelah restart.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="base">Base URL</Label>
            <Input id="base" value={cfg.base_url} onChange={(e) => setCfg({ ...cfg, base_url: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="key">API Key</Label>
            <Input id="key" type="password" placeholder="(kosongkan untuk mempertahankan)" value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="model">Model</Label>
            <Input id="model" placeholder="mis. cb/auto" value={cfg.model} onChange={(e) => setCfg({ ...cfg, model: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="mt">max_tokens</Label>
              <Input id="mt" type="number" value={cfg.max_tokens} onChange={(e) => setCfg({ ...cfg, max_tokens: parseInt(e.target.value || "512") })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to">timeout (s)</Label>
              <Input id="to" type="number" value={cfg.timeout_s} onChange={(e) => setCfg({ ...cfg, timeout_s: parseFloat(e.target.value || "60") })} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Batal</Button>
          <Button onClick={save} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Simpan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
