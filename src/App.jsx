import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Shuffle, BarChart3, Upload, RotateCcw, AlertTriangle, Copy, CheckCircle2 } from "lucide-react";

function Card({ className = "", children }) {
  return <div className={className}>{children}</div>;
}

function CardContent({ className = "", children }) {
  return <div className={className}>{children}</div>;
}

function Button({ className = "", variant, children, ...props }) {
  const base = "inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-bold transition disabled:opacity-50";
  const outline = variant === "outline" ? "border bg-transparent hover:bg-slate-800" : "";
  return (
    <button className={`${base} ${outline} ${className}`} {...props}>
      {children}
    </button>
  );
}


const STORAGE_KEY = "powerball_rng_raw_data_v1";

function drawToLine(draw) {
  return `${draw.white.map(fmt).join(" ")} ${fmt(draw.powerball)}`;
}

function drawKey(draw) {
  return `${draw.white.slice().sort((a, b) => a - b).join("-")}|${draw.powerball}`;
}

function normalizeDraw(nums) {
  const white = nums.slice(0, 5).map(Number).sort((a, b) => a - b);
  const powerball = Number(nums[5]);
  return { white, powerball };
}

function extractDrawArraysFromJson(value) {
  if (Array.isArray(value)) return value;

  if (value && typeof value === "object") {
    if (Array.isArray(value.numbers)) return value.numbers;
    if (Array.isArray(value.draws)) return value.draws;
    if (Array.isArray(value.results)) return value.results;
    if (Array.isArray(value.data)) return value.data;
  }

  return [];
}

function parseUploadText(text, fileName = "") {
  const trimmed = text.trim();
  const imported = [];
  const errors = [];

  try {
    if (fileName.toLowerCase().endsWith(".json") || trimmed.startsWith("[") || trimmed.startsWith("{")) {
      const json = JSON.parse(trimmed);
      const rows = extractDrawArraysFromJson(json);

      rows.forEach((row, index) => {
        let nums = [];

        if (Array.isArray(row)) {
          nums = row.map(Number);
        } else if (row && typeof row === "object") {
          if (Array.isArray(row.white) && row.powerball !== undefined) nums = [...row.white, row.powerball].map(Number);
          else if (Array.isArray(row.numbers)) nums = row.numbers.map(Number);
          else if (Array.isArray(row.draw)) nums = row.draw.map(Number);
        }

        if (nums.length !== 6 || nums.some(Number.isNaN)) {
          errors.push(`JSON row ${index + 1}: expected 6 numbers`);
          return;
        }

        imported.push(normalizeDraw(nums));
      });

      return { imported, errors };
    }
  } catch (err) {
    errors.push(`JSON parse error: ${err.message}`);
    return { imported, errors };
  }

  const lines = trimmed.split(/\n+/).map(l => l.trim()).filter(Boolean);
  lines.forEach((line, index) => {
    const nums = line.match(/\d+/g)?.map(Number) || [];
    if (nums.length !== 6) {
      errors.push(`Line ${index + 1}: expected 6 numbers, got ${nums.length}`);
      return;
    }
    imported.push(normalizeDraw(nums));
  });

  return { imported, errors };
}

function validateDraw(draw, indexLabel = "Draw") {
  const errors = [];
  const uniqueWhite = new Set(draw.white);

  if (draw.white.length !== 5) errors.push(`${indexLabel}: expected 5 white balls`);
  if (uniqueWhite.size !== 5) errors.push(`${indexLabel}: duplicate white ball found`);
  if (draw.white.some(n => n < 1 || n > 69)) errors.push(`${indexLabel}: white balls must be 1-69`);
  if (draw.powerball < 1 || draw.powerball > 39) errors.push(`${indexLabel}: Powerball must be 1-39 based on your mixed historical set`);

  return errors;
}


const DEFAULT_RAW = `11 21 27 36 62 24
14 18 36 49 67 18
18 31 36 43 47 20
06 24 30 53 56 19
05 18 23 40 50 18
21 37 52 53 58 05
06 10 31 37 44 23
01 03 13 44 56 26
18 20 27 45 65 06
11 28 37 40 53 13
02 06 40 42 55 24
23 32 33 45 49 14
14 16 37 48 58 18
13 15 17 45 63 13
07 15 18 32 45 20
04 05 17 43 52 05
51 54 57 60 69 11
02 57 58 60 65 26
08 12 18 44 51 18
28 31 40 41 46 04
03 04 06 48 53 10
11 14 31 47 48 04
17 54 56 63 69 20
04 23 37 61 67 07
27 32 34 43 52 13
06 13 38 39 53 06
10 24 27 35 53 18
03 43 45 61 65 14
03 04 11 41 67 05
01 20 22 60 66 03
14 26 38 45 46 13
04 19 23 25 49 14
14 20 39 65 67 02
40 53 60 68 69 22
05 08 17 27 28 14
17 33 35 42 52 09
01 02 07 52 61 04
05 37 40 64 66 05
01 16 48 49 65 08
15 39 58 63 67 07
20 28 33 63 68 20
01 15 21 32 46 01
04 08 22 32 58 04
04 33 43 53 65 21
02 28 31 44 52 18
21 40 44 50 55 16
11 31 50 52 58 18
17 18 37 44 53 18
05 11 51 56 61 02
34 38 42 61 62 19`;

function parseInput(raw) {
  const lines = raw.split(/\n+/).map(l => l.trim()).filter(Boolean);
  const draws = [];
  const errors = [];

  lines.forEach((line, index) => {
    const nums = line.match(/\d+/g)?.map(Number) || [];
    if (nums.length !== 6) {
      errors.push(`Line ${index + 1}: expected 6 numbers, got ${nums.length}`);
      return;
    }

    const draw = normalizeDraw(nums);
    errors.push(...validateDraw(draw, `Line ${index + 1}`));
    draws.push(draw);
  });

  return { draws, errors };
}

function countFreq(draws, range, type = "white") {
  const counts = Object.fromEntries(Array.from({ length: range }, (_, i) => [i + 1, 0]));
  draws.forEach(d => {
    if (type === "white") d.white.forEach(n => counts[n] = (counts[n] || 0) + 1);
    else counts[d.powerball] = (counts[d.powerball] || 0) + 1;
  });
  return counts;
}

function weightedPick(items, weights) {
  const total = items.reduce((sum, item) => sum + weights[item], 0);
  let r = Math.random() * total;
  for (const item of items) {
    r -= weights[item];
    if (r <= 0) return item;
  }
  return items[items.length - 1];
}

function buildWeights(freq, range, strength) {
  const values = Array.from({ length: range }, (_, i) => i + 1);
  const avg = values.reduce((s, n) => s + (freq[n] || 0), 0) / range || 1;
  const weights = {};
  values.forEach(n => {
    const normalized = ((freq[n] || 0) + 1) / (avg + 1);
    weights[n] = Math.pow(normalized, strength);
  });
  return weights;
}

function generateOne(draws, strength, mode) {
  const whiteFreq = countFreq(draws, 69, "white");
  const pbRange = 39;
  const pbFreq = countFreq(draws, pbRange, "pb");

  let whiteWeights = buildWeights(whiteFreq, 69, strength);
  let pbWeights = buildWeights(pbFreq, pbRange, strength);

  if (mode === "balanced") {
    for (let n = 1; n <= 69; n++) {
      const decade = Math.ceil(n / 10);
      whiteWeights[n] *= decade >= 2 && decade <= 6 ? 1.06 : 0.96;
    }
  }

  const whites = [];
  const whitePool = Array.from({ length: 69 }, (_, i) => i + 1);
  while (whites.length < 5) {
    const pick = weightedPick(whitePool.filter(n => !whites.includes(n)), whiteWeights);
    whites.push(pick);
  }

  const pbPool = Array.from({ length: pbRange }, (_, i) => i + 1);
  const pb = weightedPick(pbPool, pbWeights);
  return [...whites.sort((a, b) => a - b), pb];
}

function topEntries(freq, count = 10) {
  return Object.entries(freq)
    .map(([n, c]) => ({ n: Number(n), c }))
    .sort((a, b) => b.c - a.c || a.n - b.n)
    .slice(0, count);
}

function fmt(n) {
  return String(n).padStart(2, "0");
}

export default function PowerballWeightedRngApp() {
  const [raw, setRaw] = useState(() => localStorage.getItem(STORAGE_KEY) || DEFAULT_RAW);
  const [strength, setStrength] = useState(1.25);
  const [mode, setMode] = useState("balanced");
  const [generated, setGenerated] = useState([]);
  const [copied, setCopied] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");


  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, raw);
  }, [raw]);

  const parsed = useMemo(() => parseInput(raw), [raw]);
  const whiteFreq = useMemo(() => countFreq(parsed.draws, 69, "white"), [parsed.draws]);
  const pbFreq = useMemo(() => countFreq(parsed.draws, 39, "pb"), [parsed.draws]);
  const topWhite = useMemo(() => topEntries(whiteFreq, 12), [whiteFreq]);
  const topPb = useMemo(() => topEntries(pbFreq, 12), [pbFreq]);

  const stats = useMemo(() => {
    const sums = parsed.draws.map(d => d.white.reduce((a, b) => a + b, 0));
    const avgSum = sums.length ? Math.round(sums.reduce((a, b) => a + b, 0) / sums.length) : 0;
    const oddEven = parsed.draws.map(d => d.white.filter(n => n % 2).length);
    const avgOdd = oddEven.length ? (oddEven.reduce((a, b) => a + b, 0) / oddEven.length).toFixed(1) : "0";
    return { avgSum, avgOdd, count: parsed.draws.length };
  }, [parsed.draws]);

  const handleGenerate = (qty = 5) => {
    const picks = Array.from({ length: qty }, () => generateOne(parsed.draws, Number(strength), mode));
    setGenerated(picks);
    setCopied(false);
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const text = await file.text();
    const { imported, errors } = parseUploadText(text, file.name);

    const currentKeys = new Set(parsed.draws.map(drawKey));
    const validNew = [];
    const skipped = [];

    imported.forEach((draw, index) => {
      const validationErrors = validateDraw(draw, `Uploaded row ${index + 1}`);
      if (validationErrors.length) {
        skipped.push(...validationErrors);
        return;
      }

      const key = drawKey(draw);
      if (currentKeys.has(key)) {
        skipped.push(`Uploaded row ${index + 1}: duplicate skipped`);
        return;
      }

      currentKeys.add(key);
      validNew.push(draw);
    });

    if (validNew.length) {
      const appended = validNew.map(drawToLine).join("\n");
      setRaw(prev => `${prev.trim()}\n${appended}`.trim());
      setGenerated([]);
    }

    const statusParts = [
      `${validNew.length} new draw${validNew.length === 1 ? "" : "s"} added`,
      `${skipped.length + errors.length} skipped/error${skipped.length + errors.length === 1 ? "" : "s"}`
    ];

    setUploadStatus(statusParts.join(" • "));
    event.target.value = "";
  };

  const resetToDefault = () => {
    setRaw(DEFAULT_RAW);
    localStorage.removeItem(STORAGE_KEY);
    setGenerated([]);
    setUploadStatus("Reset to starter data");
  };

  const copyPicks = async () => {
    const text = generated.map(row => `${row.slice(0, 5).map(fmt).join(" ")} | PB ${fmt(row[5])}`).join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-amber-400/10 px-3 py-1 text-sm text-amber-200">
                <AlertTriangle className="h-4 w-4" /> RNG similarity model, not a prediction engine
              </div>
              <h1 className="text-3xl md:text-5xl font-black tracking-tight">Powerball Weighted RNG Lab</h1>
              <p className="mt-3 max-w-3xl text-slate-300">This app studies your supplied draw history, builds weighted frequency tables, and generates new sets that resemble the randomness profile of the data.</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-2xl bg-slate-800 p-4"><div className="text-2xl font-bold">{stats.count}</div><div className="text-xs text-slate-400">Draws</div></div>
              <div className="rounded-2xl bg-slate-800 p-4"><div className="text-2xl font-bold">{stats.avgSum}</div><div className="text-xs text-slate-400">Avg Sum</div></div>
              <div className="rounded-2xl bg-slate-800 p-4"><div className="text-2xl font-bold">{stats.avgOdd}</div><div className="text-xs text-slate-400">Avg Odd</div></div>
            </div>
          </div>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="lg:col-span-2 rounded-3xl border-slate-800 bg-slate-900 text-slate-100">
            <CardContent className="p-5 space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 font-bold text-xl"><Upload className="h-5 w-5" /> Number Data</div>
                <div className="flex gap-2">
                  <label className="inline-flex cursor-pointer items-center justify-center rounded-xl bg-amber-400 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-amber-300">
                    Upload JSON/CSV
                    <input type="file" accept=".json,.csv,.txt" onChange={handleUpload} className="hidden" />
                  </label>
                  <Button onClick={resetToDefault} variant="outline" className="rounded-xl border-slate-700">Reset</Button>
                </div>
              </div>
              <textarea value={raw} onChange={e => setRaw(e.target.value)} className="h-[420px] w-full rounded-2xl border border-slate-700 bg-slate-950 p-4 font-mono text-sm outline-none focus:border-amber-300" />
              {uploadStatus && <div className="rounded-2xl bg-emerald-500/10 p-3 text-sm text-emerald-200">{uploadStatus}</div>}
              {parsed.errors.length > 0 && <div className="rounded-2xl bg-red-500/10 p-3 text-sm text-red-200">{parsed.errors.slice(0, 4).join(" • ")}</div>}
            </CardContent>
          </Card>

          <div className="lg:col-span-3 space-y-6">
            <Card className="rounded-3xl border-slate-800 bg-slate-900 text-slate-100">
              <CardContent className="p-5 space-y-5">
                <div className="flex items-center gap-2 font-bold text-xl"><Shuffle className="h-5 w-5" /> Generator Controls</div>
                <div className="grid gap-4 md:grid-cols-3">
                  <label className="space-y-2">
                    <span className="text-sm text-slate-400">Weight Strength</span>
                    <input type="range" min="0" max="3" step="0.05" value={strength} onChange={e => setStrength(e.target.value)} className="w-full" />
                    <div className="text-sm font-bold">{Number(strength).toFixed(2)}</div>
                  </label>
                  <label className="space-y-2">
                    <span className="text-sm text-slate-400">Mode</span>
                    <select value={mode} onChange={e => setMode(e.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 p-3">
                      <option value="balanced">Balanced Historical</option>
                      <option value="frequency">Pure Frequency</option>
                    </select>
                  </label>
                  <div className="flex items-end gap-2">
                    <Button onClick={() => handleGenerate(10)} className="w-full rounded-xl bg-amber-400 text-slate-950 hover:bg-amber-300">Generate 10</Button>
                    <Button onClick={() => setGenerated([])} variant="outline" className="rounded-xl border-slate-700"><RotateCcw className="h-4 w-4" /></Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-3xl border-slate-800 bg-slate-900 text-slate-100">
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="font-bold text-xl">Generated Sets</div>
                  {generated.length > 0 && <Button onClick={copyPicks} variant="outline" className="rounded-xl border-slate-700">{copied ? <CheckCircle2 className="h-4 w-4 mr-2" /> : <Copy className="h-4 w-4 mr-2" />} Copy</Button>}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {generated.length === 0 ? <div className="rounded-2xl bg-slate-950 p-6 text-slate-400">Generate sets to see output here.</div> : generated.map((row, i) => (
                    <div key={i} className="rounded-2xl border border-slate-800 bg-slate-950 p-4 font-mono text-lg">
                      <span>{row.slice(0, 5).map(fmt).join("  ")}</span>
                      <span className="ml-3 rounded-full bg-amber-400 px-3 py-1 text-slate-950 font-black">{fmt(row[5])}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
              <Card className="rounded-3xl border-slate-800 bg-slate-900 text-slate-100">
                <CardContent className="p-5">
                  <div className="mb-4 flex items-center gap-2 font-bold"><BarChart3 className="h-5 w-5" /> Top White Balls</div>
                  <div className="space-y-2">{topWhite.map(x => <div key={x.n} className="flex items-center gap-3"><div className="w-8 font-mono">{fmt(x.n)}</div><div className="h-3 rounded-full bg-slate-700 flex-1 overflow-hidden"><div className="h-full bg-slate-300" style={{ width: `${Math.max(6, x.c / Math.max(...topWhite.map(t => t.c)) * 100)}%` }} /></div><div className="w-8 text-right text-slate-400">{x.c}</div></div>)}</div>
                </CardContent>
              </Card>
              <Card className="rounded-3xl border-slate-800 bg-slate-900 text-slate-100">
                <CardContent className="p-5">
                  <div className="mb-4 flex items-center gap-2 font-bold"><BarChart3 className="h-5 w-5" /> Top Powerballs</div>
                  <div className="space-y-2">{topPb.map(x => <div key={x.n} className="flex items-center gap-3"><div className="w-8 font-mono">{fmt(x.n)}</div><div className="h-3 rounded-full bg-slate-700 flex-1 overflow-hidden"><div className="h-full bg-amber-300" style={{ width: `${Math.max(6, x.c / Math.max(...topPb.map(t => t.c)) * 100)}%` }} /></div><div className="w-8 text-right text-slate-400">{x.c}</div></div>)}</div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
