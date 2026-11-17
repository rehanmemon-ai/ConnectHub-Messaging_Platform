import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(loader: (signal: AbortSignal) => Promise<T>, dependencies: React.DependencyList) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    // Network loaders intentionally reset their visible request state here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true); setError(null);
    loader(controller.signal).then((result) => { setData(result); setLoading(false); }).catch((reason) => { if (reason instanceof DOMException && reason.name === "AbortError") return; setError(reason); setLoading(false); });
    return () => controller.abort();
    // Loader is intentionally represented by its explicit dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, version]);
  return { data, setData, loading, error, reload };
}
