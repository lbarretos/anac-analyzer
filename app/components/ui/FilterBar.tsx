"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

export const EMPRESAS = [
  { value: "LATAM",  label: "LATAM" },
  { value: "GOL",    label: "GOL" },
  { value: "AZUL",   label: "Azul" },
  { value: "VOEPASS",label: "VoePass" },
  { value: "MAP",    label: "MAP" },
];

export const ANO_MIN = 2010;
export const ANO_MAX = new Date().getFullYear();

interface FilterBarProps {
  mode: "yield" | "frota";
}

export default function FilterBar({ mode }: FilterBarProps) {
  const router = useRouter();
  const params = useSearchParams();

  const selectedEmpresas = params.get("empresas")?.split(",").filter(Boolean) ?? ["LATAM", "GOL", "AZUL"];
  const anoInicio = Number(params.get("anoInicio") ?? ANO_MAX - 4);
  const anoFim    = Number(params.get("anoFim")    ?? ANO_MAX);
  const metrica   = params.get("metrica") ?? (mode === "yield" ? "yield_nominal" : "ask_por_aeronave");

  const update = useCallback((key: string, value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set(key, value);
    router.push(`?${next.toString()}`, { scroll: false });
  }, [params, router]);

  const toggleEmpresa = (sigla: string) => {
    const next = selectedEmpresas.includes(sigla)
      ? selectedEmpresas.filter(e => e !== sigla)
      : [...selectedEmpresas, sigla];
    if (next.length === 0) return;
    update("empresas", next.join(","));
  };

  const yieldMetricas = [
    { value: "yield_nominal", label: "Yield (R$/RPK)" },
    { value: "prask",         label: "PRASK (R$/ASK)" },
    { value: "load_factor",   label: "Load Factor (%)" },
  ];
  const frotaMetricas = [
    { value: "ask_por_aeronave",    label: "ASK/Aeronave" },
    { value: "ciclos_por_aeronave", label: "Ciclos/Aeronave" },
    { value: "idade_media",         label: "Idade Média (anos)" },
  ];
  const metricas = mode === "yield" ? yieldMetricas : frotaMetricas;

  return (
    <div className="flex flex-wrap gap-4 items-center p-4 rounded-lg border border-gray-800 bg-gray-900 mb-6">
      {/* Empresas */}
      <div className="flex gap-2 flex-wrap">
        <span className="text-xs text-gray-500 self-center mr-1">Empresas:</span>
        {EMPRESAS.map(e => (
          <button
            key={e.value}
            onClick={() => toggleEmpresa(e.value)}
            className={`text-xs px-3 py-1 rounded-full border transition-colors ${
              selectedEmpresas.includes(e.value)
                ? "border-blue-600 bg-blue-900/40 text-blue-300"
                : "border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {e.label}
          </button>
        ))}
      </div>

      {/* Período */}
      <div className="flex gap-2 items-center">
        <span className="text-xs text-gray-500">Período:</span>
        <select
          value={anoInicio}
          onChange={e => update("anoInicio", e.target.value)}
          className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
        >
          {Array.from({ length: ANO_MAX - ANO_MIN + 1 }, (_, i) => ANO_MIN + i).map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
        <span className="text-gray-600 text-xs">até</span>
        <select
          value={anoFim}
          onChange={e => update("anoFim", e.target.value)}
          className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
        >
          {Array.from({ length: ANO_MAX - ANO_MIN + 1 }, (_, i) => ANO_MIN + i).map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      {/* Métrica */}
      <div className="flex gap-2 items-center">
        <span className="text-xs text-gray-500">Métrica:</span>
        <select
          value={metrica}
          onChange={e => update("metrica", e.target.value)}
          className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
        >
          {metricas.map(m => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
