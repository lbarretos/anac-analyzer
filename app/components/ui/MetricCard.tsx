"use client";

interface MetricCardProps {
  label: string;
  value: string | number | null;
  unit?: string;
  delta?: number;
  deltaLabel?: string;
  loading?: boolean;
}

export default function MetricCard({
  label, value, unit, delta, deltaLabel, loading,
}: MetricCardProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900 p-4 animate-pulse">
        <div className="h-3 bg-gray-700 rounded w-24 mb-3" />
        <div className="h-7 bg-gray-700 rounded w-32" />
      </div>
    );
  }

  const isNull = value === null || value === undefined;

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-semibold text-white">
        {isNull ? <span className="text-gray-600">—</span> : (
          <>
            {typeof value === "number" ? value.toLocaleString("pt-BR", { maximumFractionDigits: 3 }) : value}
            {unit && <span className="text-sm text-gray-500 ml-1">{unit}</span>}
          </>
        )}
      </p>
      {delta !== undefined && (
        <p className={`text-xs mt-1 ${delta >= 0 ? "text-emerald-500" : "text-red-400"}`}>
          {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}% {deltaLabel}
        </p>
      )}
    </div>
  );
}
