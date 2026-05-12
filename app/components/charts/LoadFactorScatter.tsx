"use client";

import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const COLORS: Record<string, string> = {
  LATAM:  "#3b82f6",
  GOL:    "#f97316",
  AZUL:   "#10b981",
  VOEPASS:"#a855f7",
  MAP:    "#eab308",
};

interface DataPoint {
  load_factor: number;
  yield_nominal: number | null;
  prask: number | null;
  periodo?: string;
  sigla_atual: string;
}

interface Props {
  data: DataPoint[];
  empresas: string[];
  yMetrica: "yield_nominal" | "prask";
  loading?: boolean;
}

export default function LoadFactorScatter({ data, empresas, yMetrica, loading }: Props) {
  if (loading) {
    return (
      <div className="h-64 rounded-lg border border-gray-800 bg-gray-900 animate-pulse flex items-center justify-center">
        <span className="text-gray-700 text-sm">Carregando...</span>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="h-64 rounded-lg border border-gray-800 bg-gray-900 flex items-center justify-center">
        <span className="text-gray-600 text-sm">Sem dados para o período selecionado</span>
      </div>
    );
  }

  const yLabel = yMetrica === "prask" ? "PRASK (R$/ASK)" : "Yield (R$/RPK)";

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis
            dataKey="load_factor"
            type="number"
            domain={[0.4, 1]}
            tickFormatter={v => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            name="Load Factor"
          />
          <YAxis
            dataKey={yMetrica}
            type="number"
            tickFormatter={v => `R$${v.toFixed(2)}`}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "#4b5563", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 6 }}
            cursor={{ strokeDasharray: "3 3" }}
            formatter={(v: number, name: string) => [
              name === "load_factor" ? `${(v * 100).toFixed(1)}%` : `R$${v.toFixed(3)}`,
              name === "load_factor" ? "Load Factor" : yLabel,
            ]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {empresas.map(emp => (
            <Scatter
              key={emp}
              name={emp}
              data={data.filter(d => d.sigla_atual === emp && d[yMetrica] !== null)}
              fill={COLORS[emp] ?? "#6b7280"}
              opacity={0.7}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
