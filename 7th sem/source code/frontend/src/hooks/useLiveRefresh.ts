import { useEffect, useRef } from 'react';

/**
 * Keep a dashboard current: run `refresh` on mount, every `intervalMs` while the tab is
 * visible, and as soon as the user returns to the tab. Hidden tabs make no requests.
 */
export const useLiveRefresh = (refresh: () => void | Promise<void>, intervalMs: number) => {
  const latest = useRef(refresh);
  useEffect(() => {
    latest.current = refresh;
  }, [refresh]);

  useEffect(() => {
    const run = () => {
      if (document.visibilityState === 'visible') void latest.current();
    };
    run();
    const timer = window.setInterval(run, intervalMs);
    document.addEventListener('visibilitychange', run);
    window.addEventListener('focus', run);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', run);
      window.removeEventListener('focus', run);
    };
  }, [intervalMs]);
};
