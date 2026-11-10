import { useCallback, useEffect, useRef, useState } from 'react';
import { loadDataset } from '../lib/data';
import type { Dataset } from '../lib/types';

const REFRESH_MS = 60_000;

/** Loads the dataset, refreshes every minute while the app is visible and on focus. */
export function useDataset() {
  const [data, setData] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const busy = useRef(false);

  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setLoading(true);
    try {
      setData(await loadDataset());
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(() => document.visibilityState === 'visible' && refresh(), REFRESH_MS);
    const onVis = () => document.visibilityState === 'visible' && refresh();
    document.addEventListener('visibilitychange', onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [refresh]);

  return { data, loading, refresh };
}
