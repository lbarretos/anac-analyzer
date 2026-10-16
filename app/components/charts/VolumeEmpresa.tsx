"use client";

import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";

interface DataPoint {
  periodo: string;
  value: number | null;
  yoy: number | null;
}

interface Props {
  data: DataPoint[];
  empresa: string;
  loading?: boolean;
}

const formatYoy = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

export default function VolumeEmpresa({ data, empresa, loading }: Props) {
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
        <ComposedChart data={data} margin={{ top: 5, right: 50, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="colorEmpresaYoy" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="periodo" tick={{ fontSize: 11, fill: "#6b7280" }} />
          <YAxis
            yAxisId="left"
            tickFormatter={(v: number) => `${(v / 1e9).toFixed(1)} Bi`}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            label={{ value: "ASK (seat-km)", angle: -90, position: "insideLeft", fill: "#4b5563", fontSize: 11 }}
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
            formatter={(v: number, name: string) => {
              if (name === "Cresc. Y/Y") return [formatYoy(v), name];
              return [`${(v / 1e9).toFixed(2)} Bi seat-km`, empresa];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="value"
            name={empresa}
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#colorEmpresaYoy)"
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
