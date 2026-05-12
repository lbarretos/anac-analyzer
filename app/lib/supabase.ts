import { neon } from "@neondatabase/serverless";

const sql = neon(process.env.DATABASE_URL!);

export async function getDataFreshness(): Promise<string | null> {
  const rows = await sql`
    SELECT ano, mes FROM stg_stats ORDER BY ano DESC, mes DESC LIMIT 1
  `;
  if (!rows.length) return null;
  const row = rows[0] as { ano: number; mes: number };
  return `${row.ano}-${String(row.mes).padStart(2, "0")}`;
}
