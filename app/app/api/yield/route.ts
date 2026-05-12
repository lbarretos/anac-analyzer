import { NextRequest, NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";

const sql = neon(process.env.DATABASE_URL!);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const empresas = (searchParams.get("empresas") ?? "LATAM,GOL,AZUL").split(",").filter(Boolean);
  const anoInicio = Number(searchParams.get("anoInicio") ?? new Date().getFullYear() - 4);
  const anoFim = Number(searchParams.get("anoFim") ?? new Date().getFullYear());

  try {
    const rows = await sql`
      SELECT sigla_atual, nome_comercial, ano, trimestre,
             load_factor, rpk, ask, yield_nominal, prask, pax_pagos
      FROM v_yield_trimestral
      WHERE sigla_atual = ANY(${empresas})
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
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
