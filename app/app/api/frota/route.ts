import { NextRequest, NextResponse } from "next/server";
import { neon } from "@neondatabase/serverless";

const sql = neon(process.env.DATABASE_URL!);

export const revalidate = 3600;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const empresas = (searchParams.get("empresas") ?? "LATAM,GOL,AZUL").split(",").filter(Boolean);
  const anoInicio = Number(searchParams.get("anoInicio") ?? new Date().getFullYear() - 3);
  const anoFim = Number(searchParams.get("anoFim") ?? new Date().getFullYear());

  try {
    const rows = await sql`
      SELECT sigla_atual, nome_comercial, ano, mes,
             TO_CHAR(periodo, 'YYYY-MM') AS periodo,
             ask_por_aeronave, ciclos_por_aeronave, idade_media,
             aeronaves_ativas, load_factor
      FROM v_utilizacao_frota
      WHERE sigla_atual = ANY(${empresas})
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
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
