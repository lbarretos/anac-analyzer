"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import FilterBar from "../../components/ui/FilterBar";
import MetricCard from "../../components/ui/MetricCard";
import FrotaUtilizacao from "../../components/charts/FrotaUtilizacao";
import FrotaBullet from "../../components/charts/FrotaBullet";

interface FrotaRow {
  sigla_atual: string;
  nome_comercial: string;
  ano: number;
  mes: number;
  periodo: string;
  ask_por_aeronave: number | null;
  ciclos_por_aeronave: number | null;
  idade_media: number | null;
  aeronaves_ativas: number | null;
  load_factor: number | null;
}

function FrotaContent() {
  const params = useSearchParams();
  const empresas   = params.get("empresas")?.split(",").filter(Boolean) ?? ["LATAM", "GOL", "AZUL"];
  const anoInicio  = Number(params.get("anoInicio") ?? new Date().getFullYear() - 3);
  const anoFim     = Number(params.get("anoFim")    ?? new Date().getFullYear());
  const metrica    = (params.get("metrica") ?? "ask_por_aeronave") as
    "ask_por_aeronave" | "ciclos_por_aeronave" | "idade_media";

  const [rows, setRows]       = useState<FrotaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      empresas: empresas.join(","),
      anoInicio: String(anoInicio),
      anoFim: String(anoFim),
    });
    fetch(`/api/frota?${params}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: FrotaRow[]) => {
        setRows(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [empresas.join(","), anoInicio, anoFim]);

  // Pivot para time series (mensal)
  const allPeriodos = Array.from(new Set(rows.map(r => `${r.ano}-${String(r.mes).padStart(2, "0")}`)));
  const timeSeriesData = allPeriodos.map(p => {
    const [ano, mes] = p.split("-").map(Number);
    const entry: { periodo: string; [key: string]: string | number | null } = { periodo: p };
    empresas.forEach(emp => {
      const row = rows.find(r => r.sigla_atual === emp && r.ano === ano && r.mes === mes);
      entry[emp] = row ? row[metrica] : null;
    });
    return entry;
  });

  // Último mês por empresa
  const latest = rows.reduce((acc: Record<string, FrotaRow>, r) => {
    if (!acc[r.sigla_atual] || r.ano > acc[r.sigla_atual].ano ||
        (r.ano === acc[r.sigla_atual].ano && r.mes > acc[r.sigla_atual].mes)) {
      acc[r.sigla_atual] = r;
    }
    return acc;
  }, {});

  // Dados para bullet chart (atual vs média histórica)
  const bulletData = empresas.map(emp => {
    const empRows = rows.filter(r => r.sigla_atual === emp && r[metrica] !== null);
    const media = empRows.length
      ? empRows.reduce((s, r) => s + (r[metrica] as number), 0) / empRows.length
      : 0;
    const labels: Record<string, string> = {
      ask_por_aeronave:    "ASK/Aeronave",
      ciclos_por_aeronave: "Ciclos/Aeronave",
      idade_media:         "Idade Média",
    };
    return {
      empresa:          emp,
      valor_atual:      latest[emp]?.[metrica] ?? 0,
      media_historica:  media,
      label:            labels[metrica],
    };
  }).filter(d => d.valor_atual > 0);

  const metricsLabel: Record<string, string> = {
    ask_por_aeronave:    "ASK/Aeronave (M seat-km)",
    ciclos_por_aeronave: "Ciclos/Aeronave",
    idade_media:         "Idade Média (anos)",
  };

  const formatMetricValue = (value: number | null): number | null => {
    if (value === null) return null;
    if (metrica === "ask_por_aeronave") return Math.round(value / 1_000_000);
    return value;
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">A4 — Utilização de Frota</h1>
        <p className="text-sm text-gray-500 mt-1">Aviação doméstica · Granularidade mensal · Dados RAB × Estatísticos</p>
      </div>

      <FilterBar mode="frota" />

      {error && (
        <div className="mb-4 p-3 rounded-lg border border-red-900 bg-red-950/30 text-red-400 text-sm flex justify-between">
          <span>Erro ao carregar dados: {error}</span>
          <button onClick={() => window.location.reload()} className="underline">Tentar novamente</button>
        </div>
      )}

      {/* MetricCards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {empresas.map(emp => (
          <MetricCard
            key={emp}
            label={`${emp} — ${metricsLabel[metrica]}`}
            value={formatMetricValue(latest[emp]?.[metrica] ?? null)}
            loading={loading}
          />
        ))}
        <MetricCard
          label="Aeronaves ativas (última ref)"
          value={Object.values(latest).reduce((s, r) => s + (r.aeronaves_ativas ?? 0), 0) || null}
          unit="aeronaves"
          loading={loading}
        />
      </div>

      {/* Evolução temporal */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          {metricsLabel[metrica]} por empresa — {anoInicio} a {anoFim}
        </h2>
        <FrotaUtilizacao
          data={timeSeriesData}
          empresas={empresas}
          metrica={metrica}
          yLabel={metricsLabel[metrica]}
          loading={loading}
        />
      </div>

      {/* Bullet chart: atual vs média */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 mb-3">
          {metricsLabel[metrica]} — período mais recente vs. média histórica
        </h2>
        <FrotaBullet data={bulletData} metrica={metrica} loading={loading} />
      </div>
    </div>
  );
}

export default function FrotaPage() {
  return (
    <Suspense>
      <FrotaContent />
    </Suspense>
  );
}
