import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Ollive Chat",
  description: "Multi-provider streaming chatbot with inference logging",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex h-screen flex-col">
          <header className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              <span className="text-emerald-400">●</span> Ollive
            </Link>
            <nav className="flex gap-4 text-sm text-zinc-400">
              <Link href="/" className="hover:text-zinc-100">New chat</Link>
              <Link href="/conversations" className="hover:text-zinc-100">History</Link>
            </nav>
          </header>
          <main className="flex-1 overflow-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
