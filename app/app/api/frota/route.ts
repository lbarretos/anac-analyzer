import { NextRequest, NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";
import { ParamError, parseEmpresas, parseYear } from "../../../lib/params";

const sql = neon((process.env.DATABASE_URL_READONLY ?? process.env.DATABASE_URL)!);

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  let empresasStr: string;
  let anoInicio: number;
  let anoFim: number;
  try {
    empresasStr = parseEmpresas(searchParams.get("empresas"), "LATAM,GOL,AZUL");
    anoInicio = parseYear(searchParams.get("anoInicio"), new Date().getFullYear() - 3, "anoInicio");
    anoFim = parseYear(searchParams.get("anoFim"), new Date().getFullYear(), "anoFim");
  } catch (e) {
    if (e instanceof ParamError) {
      return NextResponse.json({ error: e.message }, { status: 400 });
    }
    throw e;
  }
  const empresas = empresasStr.split(",").filter(Boolean);

  try {
    const rows = await sql`
      SELECT sigla_atual, nome_comercial, ano, mes,
             TO_CHAR(periodo, 'YYYY-MM') AS periodo,
             ask_por_aeronave, ciclos_por_aeronave, idade_media,
             aeronaves_ativas, load_factor
      FROM v_utilizacao_frota
      WHERE sigla_atual = ANY(string_to_array(${empresasStr}, ','))
        AND ano >= ${anoInicio}
        AND ano <= ${anoFim}
      ORDER BY ano, mes
    `;
    const parsed = rows.map((r: Record<string, unknown>) => ({
      ...r,
      ask_por_aeronave:    r.ask_por_aeronave    != null ? Number(r.ask_por_aeronave)    : null,
      ciclos_por_aeronave: r.ciclos_por_aeronave != null ? Number(r.ciclos_por_aeronave) : null,
      idade_media:         r.idade_media         != null ? Number(r.idade_media)         : null,
      aeronaves_ativas:    r.aeronaves_ativas     != null ? Number(r.aeronaves_ativas)    : null,
      load_factor:         r.load_factor         != null ? Number(r.load_factor)         : null,
    }));
    return NextResponse.json(parsed);
  } catch (err) {
    console.error("[api/frota]", err);
    return NextResponse.json({ error: "Erro interno" }, { status: 500 });
  }
}
