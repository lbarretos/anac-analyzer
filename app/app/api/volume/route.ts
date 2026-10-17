import { NextRequest, NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";
import { ParamError, parseEmpresas, parseNatureza, parseYear } from "../../../lib/params";

const sql = neon(process.env.DATABASE_URL!);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  let empresasStr: string;
  let anoInicio: number;
  let anoFim: number;
  let natureza: string;
  try {
    empresasStr = parseEmpresas(searchParams.get("empresas"), "LATAM,GOL,AZUL");
    anoInicio = parseYear(searchParams.get("anoInicio"), new Date().getFullYear() - 4, "anoInicio");
    anoFim = parseYear(searchParams.get("anoFim"), new Date().getFullYear(), "anoFim");
    natureza = parseNatureza(searchParams.get("natureza"), "DOMÉSTICA");
  } catch (e) {
    if (e instanceof ParamError) {
      return NextResponse.json({ error: e.message }, { status: 400 });
    }
    throw e;
  }

  try {
    const [byEmpresa, setor, empresasRows] = await Promise.all([
      // Dados por empresa — query direta em stg_stats para suportar qualquer natureza
      sql`
        SELECT
          e.sigla_atual,
          e.nome_comercial,
          s.ano,
          s.mes,
          TO_CHAR(DATE_TRUNC('month', MAKE_DATE(s.ano, s.mes, 1))::DATE, 'YYYY-MM') AS periodo,
          SUM(CASE WHEN s.decolagens > 0 THEN s.passageiros_pagos * (s.distancia_km / s.decolagens) ELSE 0 END)         AS rpk,
          SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END) AS ask,
          SUM(s.passageiros_pagos)                              AS pax_pagos,
          SUM(s.decolagens)                                     AS decolagens,
          CASE WHEN SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END) > 0
            THEN SUM(CASE WHEN s.decolagens > 0 THEN s.passageiros_pagos * (s.distancia_km / s.decolagens) ELSE 0 END)::NUMERIC
               / SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END)
            ELSE NULL
          END AS load_factor
        FROM stg_stats s
        JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
        WHERE s.natureza = ${natureza}
          AND e.sigla_atual = ANY(string_to_array(${empresasStr}, ','))
          AND s.ano >= ${anoInicio}
          AND s.ano <= ${anoFim}
        GROUP BY e.sigla_atual, e.nome_comercial, s.ano, s.mes
        ORDER BY s.ano, s.mes
      `,
      // Visão setorial total (todas as empresas da natureza)
      sql`
        SELECT
          s.ano,
          s.mes,
          TO_CHAR(DATE_TRUNC('month', MAKE_DATE(s.ano, s.mes, 1))::DATE, 'YYYY-MM') AS periodo,
          SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END) AS ask_total,
          SUM(CASE WHEN s.decolagens > 0 THEN s.passageiros_pagos * (s.distancia_km / s.decolagens) ELSE 0 END)         AS rpk_total,
          SUM(s.passageiros_pagos)                              AS pax_total,
          SUM(s.decolagens)                                     AS decolagens_total,
          CASE WHEN SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END) > 0
            THEN SUM(CASE WHEN s.decolagens > 0 THEN s.passageiros_pagos * (s.distancia_km / s.decolagens) ELSE 0 END)::NUMERIC
               / SUM(CASE WHEN s.decolagens > 0 THEN s.assentos_disponibilizados * (s.distancia_km / s.decolagens) ELSE 0 END)
            ELSE NULL
          END AS load_factor_setor
        FROM stg_stats s
        JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
        WHERE s.natureza = ${natureza}
          AND s.ano >= ${anoInicio}
          AND s.ano <= ${anoFim}
        GROUP BY s.ano, s.mes
        ORDER BY s.ano, s.mes
      `,
      // Empresas disponíveis para a natureza/período (sem filtro de empresa)
      sql`
        SELECT DISTINCT e.sigla_atual, COALESCE(e.nome_comercial, e.sigla_atual) AS nome_comercial
        FROM stg_stats s
        JOIN dim_empresa e ON s.empresa_sigla = e.sigla_raw
        WHERE s.natureza = ${natureza}
          AND s.ano >= ${anoInicio}
          AND s.ano <= ${anoFim}
        ORDER BY e.sigla_atual
      `,
    ]);

    const parseRow = (r: Record<string, unknown>) => ({
      ...r,
      ask:         r.ask         != null ? Number(r.ask)         : null,
      rpk:         r.rpk         != null ? Number(r.rpk)         : null,
      pax_pagos:   r.pax_pagos   != null ? Number(r.pax_pagos)   : null,
      load_factor: r.load_factor != null ? Number(r.load_factor) : null,
      decolagens:  r.decolagens  != null ? Number(r.decolagens)  : null,
    });

    const parseSetor = (r: Record<string, unknown>) => ({
      ...r,
      ask_total:         r.ask_total         != null ? Number(r.ask_total)         : null,
      rpk_total:         r.rpk_total         != null ? Number(r.rpk_total)         : null,
      pax_total:         r.pax_total         != null ? Number(r.pax_total)         : null,
      decolagens_total:  r.decolagens_total  != null ? Number(r.decolagens_total)  : null,
      load_factor_setor: r.load_factor_setor != null ? Number(r.load_factor_setor) : null,
    });

    return NextResponse.json({
      byEmpresa: byEmpresa.map(parseRow),
      setor: setor.map(parseSetor),
      empresasDisponiveis: empresasRows.map(r => ({
        value: r.sigla_atual as string,
        label: r.nome_comercial as string,
      })),
    });
  } catch (err) {
    console.error("[api/volume]", err);
    return NextResponse.json({ error: "Erro interno" }, { status: 500 });
  }
}
