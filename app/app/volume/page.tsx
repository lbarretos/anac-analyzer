"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import FilterBar from "../../components/ui/FilterBar";
import MetricCard from "../../components/ui/MetricCard";
import VolumeLinhas from "../../components/charts/VolumeLinhas";
import VolumeEmpresa from "../../components/charts/VolumeEmpresa";
import VolumeSetor from "../../components/charts/VolumeSetor";

interface VolumeRow {
  sigla_atual: string;
  nome_comercial: string;
  ano: number;
  mes: number;
  periodo: string;
  ask: number | null;
  rpk: number | null;
  pax_pagos: number | null;
  load_factor: number | null;
  decolagens: number | null;
}

interface SetorRow {
  periodo: string;
  ask_total: number | null;
  rpk_total: number | null;
  pax_total: number | null;
  load_factor_setor: number | null;
}

interface EmpresaOption {
  value: string;
  label: string;
}

interface ApiResponse {
  byEmpresa: VolumeRow[];
  setor: SetorRow[];
  empresasDisponiveis: EmpresaOption[];
}

const NATUREZAS = [
  { value: "DOMÉSTICA",      label: "Doméstico" },
  { value: "INTERNACIONAL",  label: "Internacional" },
];

function VolumeContent() {
  const router = useRouter();
  const params = useSearchParams();

  const natureza  = params.get("natureza")  ?? "DOMÉSTICA";
  const empresas  = params.get("empresas")?.split(",").filter(Boolean) ?? ["LATAM", "GOL", "AZUL"];
  const anoInicio = Number(params.get("anoInicio") ?? new Date().getFullYear() - 4);
  const anoFim    = Number(params.get("anoFim")    ?? new Date().getFullYear());
  const metrica   = (params.get("metrica") ?? "ask_total") as
    "ask_total" | "pax_total" | "load_factor_setor";

  const [byEmpresa, setByEmpresa]               = useState<VolumeRow[]>([]);
  const [setor, setSetor]                       = useState<SetorRow[]>([]);
  const [empresasDisponiveis, setEmpresasDisp]  = useState<EmpresaOption[]>([]);
  const [loading, setLoading]                   = useState(true);
  const [error, setError]                       = useState<string | null>(null);
  const [empresaSingle, setEmpresaSingle]       = useState<string>(empresas[0]);

  // Sync empresaSingle when empresa filter changes
  useEffect(() => {
    if (!empresas.includes(empresaSingle)) setEmpresaSingle(empresas[0]);
  }, [empresas.join(",")]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const qs = new URLSearchParams({
      empresas: empresas.join(","),
      anoInicio: String(anoInicio),
      anoFim: String(anoFim),
      natureza,
    });
    fetch(`/api/volume?${qs}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ApiResponse) => {
        setByEmpresa(data.byEmpresa);
        setSetor(data.setor);
        setEmpresasDisp(data.empresasDisponiveis ?? []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [empresas.join(","), anoInicio, anoFim, natureza]);

  const handleNaturezaChange = (newNatureza: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("natureza", newNatureza);
    next.set("empresas", "LATAM,GOL,AZUL");
    router.push(`?${next.toString()}`, { scroll: false });
  };

  // Pivot byEmpresa → time series for VolumeLinhas
  const allPeriodos = useMemo(
    () => Array.from(new Set(byEmpresa.map(r => r.periodo))).sort(),
    [byEmpresa]
  );

  const timeSeriesData = useMemo(() =>
    allPeriodos.map(p => {
      const entry: { periodo: string; [key: string]: string | number | null } = { periodo: p };
      empresas.forEach(emp => {
        const row = byEmpresa.find(r => r.sigla_atual === emp && r.periodo === p);
        entry[emp] = row?.ask ?? null;
      });
      return entry;
    }),
    [allPeriodos, byEmpresa, empresas.join(",")]
  );

  // Single empresa series with Y/Y growth
  const empresaSingleData = useMemo(() => {
    const rows = byEmpresa
      .filter(r => r.sigla_atual === empresaSingle)
      .sort((a, b) => a.periodo.localeCompare(b.periodo));
    return rows.map(row => {
      const [y, m] = row.periodo.split("-").map(Number);
      const prevPeriod = `${y - 1}-${String(m).padStart(2, "0")}`;
      const prev = rows.find(r => r.periodo === prevPeriod);
      const curr = row.ask;
      const prevVal = prev?.ask ?? null;
      const yoy = (curr != null && prevVal != null && prevVal !== 0)
        ? ((curr - prevVal) / prevVal) * 100
        : null;
      return { periodo: row.periodo, value: curr, yoy };
    });
  }, [byEmpresa, empresaSingle]);

  // Latest entry per empresa for KPI cards
  const latest = useMemo(() =>
    byEmpresa.reduce((acc: Record<string, VolumeRow>, r) => {
      if (!acc[r.sigla_atual] || r.ano > acc[r.sigla_atual].ano ||
          (r.ano === acc[r.sigla_atual].ano && r.mes > acc[r.sigla_atual].mes)) {
        acc[r.sigla_atual] = r;
      }
      return acc;
    }, {}),
    [byEmpresa]
  );

  const latestSetor = setor[setor.length - 1];
  const formatAsk = (v: number | null) => v != null ? Math.round(v / 1e9) : null;

  // Empresa options for FilterBar: use dynamic list once loaded, fallback to selected
  const empresasOpcoes: EmpresaOption[] = empresasDisponiveis.length > 0
    ? empresasDisponiveis
    : empresas.map(e => ({ value: e, label: e }));

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">A2 — Volume Mensal</h1>
        <p className="text-sm text-gray-500 mt-1">
          Aviação doméstica · ASK, passageiros e load factor · Granularidade mensal
        </p>
      </div>

      {/* Seletor de natureza */}
      <div className="flex gap-1 mb-4">
        {NATUREZAS.map(n => (
          <button
            key={n.value}
            onClick={() => handleNaturezaChange(n.value)}
            className={`text-sm px-4 py-1.5 rounded-full border transition-colors ${
              natureza === n.value
                ? "border-blue-600 bg-blue-900/40 text-blue-300 font-medium"
                : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200"
            }`}
          >
            {n.label}
          </button>
        ))}
      </div>

      <FilterBar mode="volume" empresasOpcoes={empresasOpcoes} />

      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-900 bg-red-950/30 text-red-400 text-sm flex justify-between">
          <span>Erro ao carregar dados: {error}</span>
          <button onClick={() => window.location.reload()} className="underline">Tentar novamente</button>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {empresas.map(emp => (
          <MetricCard
            key={emp}
            label={`${emp} — ASK (Bi seat-km)`}
            value={formatAsk(latest[emp]?.ask ?? null)}
            loading={loading}
          />
        ))}
        <MetricCard
          label="ASK Setorial (Bi seat-km)"
          value={formatAsk(latestSetor?.ask_total ?? null)}
          loading={loading}
        />
      </div>

      {/* ASK por empresa — visão comparativa */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          ASK por empresa (seat-km) — {anoInicio} a {anoFim}
        </h2>
        <VolumeLinhas
          data={timeSeriesData}
          empresas={empresas}
          loading={loading}
        />
      </div>

      {/* Análise por empresa com crescimento Y/Y */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <h2 className="text-sm font-semibold text-gray-400">
            ASK + crescimento Y/Y —
          </h2>
          <select
            value={empresaSingle}
            onChange={e => setEmpresaSingle(e.target.value)}
            className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
          >
            {empresas.map(emp => (
              <option key={emp} value={emp}>{emp}</option>
            ))}
          </select>
        </div>
        <VolumeEmpresa
          data={empresaSingleData}
          empresa={empresaSingle}
          loading={loading}
        />
      </div>

      {/* Visão setorial */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          Visão setorial + crescimento Y/Y — {anoInicio} a {anoFim}
        </h2>
        <VolumeSetor
          data={setor}
          metrica={metrica}
          loading={loading}
        />
      </div>
    </div>
  );
}

export default function VolumePage() {
  return (
    <Suspense>
      <VolumeContent />
    </Suspense>
  );
}
