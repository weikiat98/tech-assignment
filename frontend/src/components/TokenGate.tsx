import type { ReactNode } from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, getToken, setToken } from "../lib/api";

/** Passphrase screen shown only when the deployment requires APP_ACCESS_TOKEN. */
export default function TokenGate({ children }: { children: ReactNode }) {
  const { data, isLoading, error } = useQuery({ queryKey: ["public-config"], queryFn: api.publicConfig });
  const [value, setValue] = useState("");
  const [unlocked, setUnlocked] = useState(Boolean(getToken()));

  if (isLoading) return <p className="text-sm text-muted">Connecting…</p>;
  if (error) return <p className="text-sm text-danger">Cannot reach the API: {(error as Error).message}</p>;
  if (!data?.token_required || unlocked) return <>{children}</>;

  return (
    <form
      className="mx-auto mt-24 max-w-sm rounded-lg border border-line bg-surface p-6"
      onSubmit={(e) => {
        e.preventDefault();
        setToken(value.trim());
        setUnlocked(true);
      }}
    >
      <h1 className="text-lg font-semibold">Access required</h1>
      <p className="mt-1 text-sm text-muted">Enter the access token for this deployment.</p>
      <input
        type="password"
        aria-label="Access token"
        className="mt-4 w-full rounded-md border border-line-strong bg-canvas px-3 py-2 text-sm text-ink"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      <button className="mt-4 w-full rounded-md bg-brand-600 py-2 text-sm font-medium text-on-brand hover:bg-brand-700">
        Continue
      </button>
    </form>
  );
}
