import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ANAC Aviation Analytics",
  description: "Análise de dados públicos da aviação doméstica brasileira",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className={`${inter.className} bg-gray-950 text-gray-100 min-h-screen`}>
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
          <Link href="/" className="font-semibold text-white hover:text-blue-400 transition-colors">
            ANAC Analytics
          </Link>
          <Link href="/yield" className="text-sm text-gray-400 hover:text-white transition-colors">
            A1 — Yield & PRASK
          </Link>
          <Link href="/frota" className="text-sm text-gray-400 hover:text-white transition-colors">
            A4 — Utilização de Frota
          </Link>
          <span className="ml-auto text-xs text-gray-600">
            Dados públicos ANAC · Valores nominais sem ajuste de inflação
          </span>
        </nav>
        <main className="px-6 py-6 max-w-7xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
