"use client";

import { useEffect, useState } from "react";
import { getProviders, type ProvidersResponse } from "@/lib/api";

export type Selection = { provider: string; model: string };

export function ProviderPicker({
  value,
  onChange,
}: {
  value: Selection | null;
  onChange: (s: Selection) => void;
}) {
  const [data, setData] = useState<ProvidersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProviders()
      .then((d) => {
        setData(d);
        if (!value && d.providers.length > 0) {
          const first = d.providers[0];
          onChange({ provider: first.name, model: first.models[0] });
        }
      })
      .catch((e) => setError(String(e)));
  }, [onChange, value]);

  if (error) return <div className="text-xs text-red-400">providers: {error}</div>;
  if (!data) return <div className="text-xs text-zinc-500">loading providers…</div>;

  if (data.providers.length === 0) {
    return (
      <div className="text-xs text-amber-400">
        No provider API keys configured. Set OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY.
      </div>
    );
  }

  const current = value ?? { provider: data.providers[0].name, model: data.providers[0].models[0] };
  const models = data.providers.find((p) => p.name === current.provider)?.models ?? [];

  return (
    <div className="flex gap-2 text-sm">
      <select
        value={current.provider}
        onChange={(e) => {
          const p = data.providers.find((x) => x.name === e.target.value)!;
          onChange({ provider: p.name, model: p.models[0] });
        }}
        className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
      >
        {data.providers.map((p) => (
          <option key={p.name} value={p.name}>{p.name}</option>
        ))}
      </select>
      <select
        value={current.model}
        onChange={(e) => onChange({ provider: current.provider, model: e.target.value })}
        className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
      >
        {models.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
    </div>
  );
}
