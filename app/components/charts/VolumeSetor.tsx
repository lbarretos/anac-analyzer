"use client";

import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

interface SetorRow {
  periodo: string;
  ask_total: number | null;
  rpk_total: number | null;
  pax_total: number | null;
  load_factor_setor: number | null;
}

interface Props {
  data: SetorRow[];
  metrica: "ask_total" | "pax_total" | "load_factor_setor";
  loading?: boolean;
}

const LABELS: Record<string, string> = {
  ask_total:         "ASK Total (seat-km)",
  pax_total:         "Passageiros Pagos",
  load_factor_setor: "Load Factor Setorial",
};

const formatYoy = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

export default function VolumeSetor({ data, metrica, loading }: Props) {
  if (loading) {
    return (
      <div className="h-72 rounded-lg border border-gray-800 bg-gray-900 animate-pulse flex items-center justify-center">
        <span className="text-gray-700 text-sm">Carregando...</span>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="h-72 rounded-lg border border-gray-800 bg-gray-900 flex items-center justify-center">
        <span className="text-gray-600 text-sm">Sem dados para o período selecionado</span>
      </div>
    );
  }

  const dataWithYoY = data.map(row => {
    const [y, m] = row.periodo.split("-").map(Number);
    const prevPeriod = `${y - 1}-${String(m).padStart(2, "0")}`;
    const prev = data.find(r => r.periodo === prevPeriod);
    const curr = row[metrica];
    const prevVal = prev?.[metrica] ?? null;
    const yoy = (curr != null && prevVal != null && prevVal !== 0)
      ? ((curr - prevVal) / Math.abs(prevVal)) * 100
      : null;
    return { ...row, yoy };
  });

  const formatY = (v: number) => {
    if (metrica === "load_factor_setor") return `${(v * 100).toFixed(1)}%`;
    if (metrica === "pax_total") return `${(v / 1e6).toFixed(1)} M`;
    return `${(v / 1e9).toFixed(1)} Bi`;
  };

  const formatTooltip = (v: number, name: string) => {
    if (name === "Cresc. Y/Y") return [formatYoy(v), name];
    if (metrica === "load_factor_setor") return [`${(v * 100).toFixed(1)}%`, LABELS[metrica]];
    if (metrica === "pax_total") return [`${(v / 1e6).toFixed(2)} M pax`, LABELS[metrica]];
    return [`${(v / 1e9).toFixed(2)} Bi seat-km`, LABELS[metrica]];
  };

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={dataWithYoY} margin={{ top: 5, right: 50, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="colorSetor" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="periodo" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis
            yAxisId="left"
            tickFormatter={formatY}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            label={{ value: LABELS[metrica], angle: -90, position: "insideLeft", fill: "#4b5563", fontSize: 11 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={formatYoy}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            label={{ value: "Cresc. Y/Y", angle: 90, position: "insideRight", fill: "#4b5563", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 6 }}
            formatter={(v: number, name: string) => formatTooltip(v, name)}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey={metrica}
            name={LABELS[metrica]}
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#colorSetor)"
            dot={false}
            connectNulls={false}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="yoy"
            name="Cresc. Y/Y"
            stroke="#f97316"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
