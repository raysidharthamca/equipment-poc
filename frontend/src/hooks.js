import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Poll an async loader on an interval so status flips appear without a manual
 * refresh — the "card turns green live" moment for the demo.
 */
export function usePolling(loader, intervalMs = 5000, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const savedLoader = useRef(loader);
  savedLoader.current = loader;

  const refresh = useCallback(async () => {
    try {
      const result = await savedLoader.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refresh();
    if (!intervalMs) return;
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
