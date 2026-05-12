import Link from "next/link";
import { getDataFreshness } from "../lib/supabase";

export const revalidate = 3600;

export default async function HomePage() {
  const freshness = await getDataFreshness();

  return (
    <div className="py-12">
      <h1 className="text-3xl font-bold text-white mb-2">ANAC Aviation Analytics</h1>
      <p className="text-gray-400 mb-2">
        Dados públicos da aviação doméstica brasileira — 2010 até o presente.
      </p>
      {freshness && (
        <p className="text-xs text-gray-600 mb-10">
          Dados até: <span className="text-gray-400">{freshness}</span> · Atualização mensal automática
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        <Link
          href="/yield"
          className="block p-6 rounded-xl border border-gray-800 hover:border-blue-700 hover:bg-gray-900 transition-all group"
        >
          <div className="text-xs text-blue-500 font-mono mb-2">Análise A1</div>
          <h2 className="text-xl font-semibold text-white mb-2 group-hover:text-blue-300">
            Yield & PRASK
          </h2>
          <p className="text-sm text-gray-400">
            Yield nominal (R$/RPK) e PRASK (R$/ASK) por empresa, por trimestre.
            Inclui load factor e volume de passageiros pagos.
          </p>
          <p className="text-xs text-gray-600 mt-4">
            Fontes: Dados Estatísticos × Tarifas Domésticas
          </p>
        </Link>

        <Link
          href="/frota"
          className="block p-6 rounded-xl border border-gray-800 hover:border-emerald-700 hover:bg-gray-900 transition-all group"
        >
          <div className="text-xs text-emerald-500 font-mono mb-2">Análise A4</div>
          <h2 className="text-xl font-semibold text-white mb-2 group-hover:text-emerald-300">
            Utilização de Frota
          </h2>
          <p className="text-sm text-gray-400">
            ASK por aeronave, ciclos por aeronave e idade média da frota.
            Compara eficiência operacional entre empresas ao longo do tempo.
          </p>
          <p className="text-xs text-gray-600 mt-4">
            Fontes: Dados Estatísticos × RAB
          </p>
        </Link>
      </div>

      <div className="mt-10 p-4 rounded-lg border border-yellow-900/40 bg-yellow-950/20 text-xs text-yellow-600">
        <strong className="text-yellow-500">Nota metodológica:</strong>{" "}
        Yield e PRASK são estimativas baseadas em tarifas amostrais da ANAC (tarifa mediana de mercado × passageiros),
        não em receita contábil auditada das companhias. Valores nominais sem ajuste pelo IPCA.
        Dados de 2010 em diante.
      </div>
    </div>
  );
}
