"use client";

import Link from "next/link";
import useSWR from "swr";

import { listConversations, type Conversation } from "@/lib/api";

export function ConvList() {
  const { data, error, isLoading, mutate } = useSWR<Conversation[]>(
    "conversations",
    () => listConversations(),
    { refreshInterval: 5000 },
  );

  if (isLoading) return <div className="p-6 text-zinc-500">loading…</div>;
  if (error) return <div className="p-6 text-red-400">failed to load</div>;
  if (!data || data.length === 0) {
    return (
      <div className="p-6 text-zinc-500">
        No conversations yet. <Link href="/" className="text-emerald-400 hover:underline">Start one</Link>.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Conversations</h2>
        <button onClick={() => mutate()} className="text-xs text-zinc-400 hover:text-zinc-100">refresh</button>
      </div>
      <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800">
        {data.map((c) => (
          <li key={c.id}>
            <Link href={`/c/${c.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-zinc-900">
              <div>
                <div className="text-sm font-medium">{c.title ?? "(untitled)"}</div>
                <div className="text-xs text-zinc-500">
                  {c.provider ?? "—"} · {c.model ?? "—"} · {new Date(c.updated_at).toLocaleString()}
                </div>
              </div>
              <StatusBadge status={c.status} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "active" ? "bg-emerald-500/20 text-emerald-300"
    : status === "cancelled" ? "bg-amber-500/20 text-amber-300"
    : "bg-zinc-700/40 text-zinc-300";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${color}`}>{status}</span>
  );
}
