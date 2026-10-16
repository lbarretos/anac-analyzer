"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

const COLORS: Record<string, string> = {
  LATAM:   "#3b82f6",
  GOL:     "#f97316",
  AZUL:    "#10b981",
  VOEPASS: "#a855f7",
  MAP:     "#eab308",
};

interface DataPoint {
  periodo: string;
  [empresa: string]: string | number | null;
}

interface Props {
  data: DataPoint[];
  empresas: string[];
  loading?: boolean;
}

const fmt = (v: number) => `${(v / 1e9).toFixed(1)} Bi`;

export default function VolumeLinhas({ data, empresas, loading }: Props) {
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

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="periodo" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis
            tickFormatter={fmt}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            label={{ value: "ASK (seat-km)", angle: -90, position: "insideLeft", fill: "#4b5563", fontSize: 11 }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 6 }}
            formatter={(v: number) => [fmt(v), ""]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {empresas.map(emp => (
            <Line
              key={emp}
              type="monotone"
              dataKey={emp}
              stroke={COLORS[emp] ?? "#6b7280"}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
