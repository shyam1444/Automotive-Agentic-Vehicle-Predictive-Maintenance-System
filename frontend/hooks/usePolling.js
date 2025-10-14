import { useEffect, useCallback, useRef } from 'react';

/**
 * Hook for polling API endpoints at regular intervals
 */
export const usePolling = (fetchFunction, interval = 5000, enabled = true) => {
  const intervalRef = useRef(null);
  const isMountedRef = useRef(true);

  const poll = useCallback(async () => {
    if (!isMountedRef.current) return;
    
    try {
      await fetchFunction();
    } catch (error) {
      console.error('Polling error:', error);
    }
  }, [fetchFunction]);

  useEffect(() => {
    isMountedRef.current = true;

    if (enabled) {
      // Initial fetch
      poll();

      // Set up interval
      intervalRef.current = setInterval(poll, interval);
    }

    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [poll, interval, enabled]);

  return { poll };
};

export default usePolling;
