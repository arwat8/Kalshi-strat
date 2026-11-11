import { useCallback, useEffect, useState } from 'react';

type Theme = 'dark' | 'light';
const KEY = 'fedstrip.theme';

function systemTheme(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function saved(): Theme | null {
  try {
    const t = localStorage.getItem(KEY);
    return t === 'dark' || t === 'light' ? t : null;
  } catch {
    return null;
  }
}

/** Follows the OS until the user picks; the pick is remembered per device. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => saved() ?? systemTheme());

  useEffect(() => {
    if (saved()) return;
    const mq = window.matchMedia?.('(prefers-color-scheme: light)');
    const on = () => setTheme(mq.matches ? 'light' : 'dark');
    mq?.addEventListener?.('change', on);
    return () => mq?.removeEventListener?.('change', on);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute('content', theme === 'dark' ? '#000000' : '#ffffff'));
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const n: Theme = t === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(KEY, n);
      } catch {
        /* storage unavailable: theme still switches for this session */
      }
      return n;
    });
  }, []);

  return { theme, toggle };
}
