"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import FilterBar from "../../components/ui/FilterBar";
import MetricCard from "../../components/ui/MetricCard";
import YieldTimeSeries from "../../components/charts/YieldTimeSeries";
import LoadFactorScatter from "../../components/charts/LoadFactorScatter";

interface YieldRow {
  sigla_atual: string;
  nome_comercial: string;
  ano: number;
  trimestre: number;
  load_factor: number | null;
  rpk: number | null;
  ask: number | null;
  yield_nominal: number | null;
  prask: number | null;
  pax_pagos: number | null;
}

function periodoLabel(ano: number, tri: number) {
  return `${ano}-T${tri}`;
}

function YieldContent() {
  const params = useSearchParams();
  const empresas   = params.get("empresas")?.split(",").filter(Boolean) ?? ["LATAM", "GOL", "AZUL"];
  const anoInicio  = Number(params.get("anoInicio") ?? new Date().getFullYear() - 4);
  const anoFim     = Number(params.get("anoFim")    ?? new Date().getFullYear());
  const metrica    = (params.get("metrica") ?? "yield_nominal") as "yield_nominal" | "prask" | "load_factor";

  const [rows, setRows]     = useState<YieldRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      empresas: empresas.join(","),
      anoInicio: String(anoInicio),
      anoFim: String(anoFim),
    });
    fetch(`/api/yield?${params}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: YieldRow[]) => {
        setRows(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [empresas.join(","), anoInicio, anoFim]);

  // Pivot para time series
  const allPeriodos = Array.from(new Set(rows.map(r => periodoLabel(r.ano, r.trimestre))));
  const timeSeriesData = allPeriodos.map(p => {
    const [ano, t] = p.split("-T").map(Number);
    const entry: { periodo: string; [key: string]: string | number | null } = { periodo: p };
    empresas.forEach(emp => {
      const row = rows.find(r => r.sigla_atual === emp && r.ano === ano && r.trimestre === t);
      entry[emp] = row ? row[metrica] : null;
    });
    return entry;
  });

  // Cards com último trimestre disponível
  const latest = rows.reduce((acc: Record<string, YieldRow>, r) => {
    if (!acc[r.sigla_atual] || r.ano > acc[r.sigla_atual].ano ||
        (r.ano === acc[r.sigla_atual].ano && r.trimestre > acc[r.sigla_atual].trimestre)) {
      acc[r.sigla_atual] = r;
    }
    return acc;
  }, {});

  const metricsLabel: Record<string, string> = {
    yield_nominal: "Yield Nominal",
    prask:         "PRASK",
    load_factor:   "Load Factor",
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">A1 — Yield & PRASK</h1>
        <p className="text-sm text-gray-500 mt-1">Aviação doméstica · Granularidade trimestral · Valores nominais</p>
      </div>

      <FilterBar mode="yield" />

      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-900 bg-red-950/30 text-red-400 text-sm flex justify-between">
          <span>Erro ao carregar dados: {error}</span>
          <button onClick={() => window.location.reload()} className="underline">Tentar novamente</button>
        </div>
      )}

      {/* MetricCards: último trimestre por empresa */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {empresas.map(emp => (
          <MetricCard
            key={emp}
            label={`${emp} — ${metricsLabel[metrica]}`}
            value={latest[emp]?.[metrica] ?? null}
            unit={metrica === "load_factor" ? "%" : "R$"}
            loading={loading}
          />
        ))}
        <MetricCard
          label="Período mais recente"
          value={Object.values(latest)[0]
            ? periodoLabel((Object.values(latest)[0] as YieldRow).ano, (Object.values(latest)[0] as YieldRow).trimestre)
            : null}
          loading={loading}
        />
      </div>

      {/* Gráfico principal: evolução temporal */}
      <div className="mb-6">
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          {metricsLabel[metrica]} por empresa — {anoInicio} a {anoFim}
        </h2>
        <YieldTimeSeries
          data={timeSeriesData}
          empresas={empresas}
          metrica={metrica}
          yLabel={metricsLabel[metrica]}
          loading={loading}
        />
      </div>

      {/* Scatter: load factor × yield */}
      {metrica !== "load_factor" && (
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3">
            Load Factor × {metricsLabel[metrica]} (por trimestre-empresa)
          </h2>
          <LoadFactorScatter
            data={rows.filter(r => r.load_factor !== null)}
            empresas={empresas}
            yMetrica={metrica === "prask" ? "prask" : "yield_nominal"}
            loading={loading}
          />
        </div>
      )}

      {rows.length === 0 && !loading && !error && (
        <p className="text-center text-gray-600 text-sm mt-8">
          Nenhuma dado encontrado. Verifique se o ETL foi executado e as views materializadas estão populadas.
        </p>
      )}
    </div>
  );
}

export default function YieldPage() {
  return (
    <Suspense>
      <YieldContent />
    </Suspense>
  );
}
