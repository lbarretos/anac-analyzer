import { NextRequest, NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";
import { ParamError, parseEmpresas, parseYear } from "../../../lib/params";

const sql = neon(process.env.DATABASE_URL!);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  let empresasStr: string;
  let anoInicio: number;
  let anoFim: number;
  try {
    empresasStr = parseEmpresas(searchParams.get("empresas"), "LATAM,GOL,AZUL");
    anoInicio = parseYear(searchParams.get("anoInicio"), new Date().getFullYear() - 4, "anoInicio");
    anoFim = parseYear(searchParams.get("anoFim"), new Date().getFullYear(), "anoFim");
  } catch (e) {
    if (e instanceof ParamError) {
      return NextResponse.json({ error: e.message }, { status: 400 });
    }
    throw e;
  }

  try {
    const rows = await sql`
      SELECT sigla_atual, nome_comercial, ano, trimestre,
             load_factor, rpk, ask, yield_nominal, prask, pax_pagos
      FROM v_yield_trimestral
      WHERE sigla_atual = ANY(string_to_array(${empresasStr}, ','))
        AND ano >= ${anoInicio}
        AND ano <= ${anoFim}
      ORDER BY ano, trimestre
    `;
    const parsed = rows.map((r: Record<string, unknown>) => ({
      ...r,
      load_factor:   r.load_factor   != null ? Number(r.load_factor)   : null,
      rpk:           r.rpk           != null ? Number(r.rpk)           : null,
      ask:           r.ask           != null ? Number(r.ask)           : null,
      yield_nominal: r.yield_nominal != null ? Number(r.yield_nominal) : null,
      prask:         r.prask         != null ? Number(r.prask)         : null,
      pax_pagos:     r.pax_pagos     != null ? Number(r.pax_pagos)     : null,
    }));
    return NextResponse.json(parsed);
  } catch (err) {
    console.error("[api/yield]", err);
    return NextResponse.json({ error: "Erro interno" }, { status: 500 });
  }
}
