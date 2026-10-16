// Validação de query params das rotas /api/*.
// Os valores já entram no SQL via template tag parametrizado (sem SQL injection);
// aqui limitamos formato e tamanho para evitar NaN, payloads grandes e abuso.

const MIN_YEAR = 1990;
const MAX_EMPRESAS = 30;
const EMPRESA_RE = /^[A-Za-z0-9_-]{1,12}$/;
const NATUREZA_RE = /^[A-Za-zÀ-ÖØ-öø-ÿ _-]{1,32}$/;

export class ParamError extends Error {}

export function parseEmpresas(raw: string | null, fallback: string): string {
  const list = (raw ?? fallback)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  // Lista vazia é válida (a UI pode desmarcar todas): a query simplesmente não retorna linhas.
  if (list.length > MAX_EMPRESAS) {
    throw new ParamError("empresas: máximo de 30 siglas");
  }
  if (!list.every((s) => EMPRESA_RE.test(s))) {
    throw new ParamError("empresas: formato inválido");
  }
  return list.join(",");
}

export function parseYear(raw: string | null, fallback: number, name: string): number {
  const n = raw === null ? fallback : Number(raw);
  const max = new Date().getFullYear() + 1;
  if (!Number.isInteger(n) || n < MIN_YEAR || n > max) {
    throw new ParamError(`${name}: ano inválido`);
  }
  return n;
}

export function parseNatureza(raw: string | null, fallback: string): string {
  const v = (raw ?? fallback).trim();
  if (!NATUREZA_RE.test(v)) throw new ParamError("natureza: formato inválido");
  return v;
}
