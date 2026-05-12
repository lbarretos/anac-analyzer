"use client";

// Bullet chart: compara valor atual de cada empresa contra sua própria média histórica.
// Substitui o GaugeEvolution do spec original (gauge não mostra evolução temporal).

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ReferenceLine, ResponsiveContainer } from "recharts";

const COLORS: Record<string, string> = {
  LATAM:  "#3b82f6",
  GOL:    "#f97316",
  AZUL:   "#10b981",
  VOEPASS:"#a855f7",
  MAP:    "#eab308",
};

interface BulletDatum {
  empresa: string;
  valor_atual: number;
  media_historica: number;
  label: string;
}

interface Props {
  data: BulletDatum[];
  metrica: string;
  loading?: boolean;
}

export default function FrotaBullet({ data, metrica, loading }: Props) {
  if (loading) {
    return (
      <div className="h-48 rounded-lg border border-gray-800 bg-gray-900 animate-pulse flex items-center justify-center">
        <span className="text-gray-700 text-sm">Carregando...</span>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="h-48 rounded-lg border border-gray-800 bg-gray-900 flex items-center justify-center">
        <span className="text-gray-600 text-sm">Sem dados disponíveis</span>
      </div>
    );
  }

  const formatV = (v: number) => {
    if (metrica === "idade_media") return `${v.toFixed(1)}a`;
    if (metrica === "ciclos_por_aeronave") return v.toFixed(1);
    return v.toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  };

  return (
    <div>
      <p className="text-xs text-gray-600 mb-2">
        Barra = valor mais recente · Linha = média histórica
      </p>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 30, left: 50, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
            <XAxis type="number" tickFormatter={formatV} tick={{ fontSize: 11, fill: "#6b7280" }} />
            <YAxis type="category" dataKey="empresa" tick={{ fontSize: 12, fill: "#9ca3af" }} width={55} />
            <Tooltip
              contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: 6 }}
              formatter={(v: number, _name: string, entry: { payload: BulletDatum }) => [
                `${formatV(v)} (média: ${formatV(entry.payload.media_historica)})`,
                entry.payload.label,
              ]}
            />
            <Bar dataKey="valor_atual" radius={[0, 4, 4, 0]}>
              {data.map(d => (
                <Cell key={d.empresa} fill={COLORS[d.empresa] ?? "#6b7280"} />
              ))}
            </Bar>
            {data.map(d => (
              <ReferenceLine
                key={d.empresa}
                x={d.media_historica}
                stroke={COLORS[d.empresa] ?? "#6b7280"}
                strokeDasharray="4 2"
                strokeOpacity={0.5}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
