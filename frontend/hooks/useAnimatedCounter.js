import { useState, useEffect, useRef } from 'react';

/**
 * Hook for animated counter with easing
 */
export const useAnimatedCounter = (targetValue, duration = 1000) => {
  const [displayValue, setDisplayValue] = useState(0);
  const frameRef = useRef();
  const startTimeRef = useRef();
  const startValueRef = useRef(0);

  useEffect(() => {
    startValueRef.current = displayValue;
    startTimeRef.current = Date.now();

    const animate = () => {
      const now = Date.now();
      const elapsed = now - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out cubic)
      const easeOutCubic = 1 - Math.pow(1 - progress, 3);

      const currentValue =
        startValueRef.current +
        (targetValue - startValueRef.current) * easeOutCubic;

      setDisplayValue(Math.round(currentValue));

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate);
      }
    };

    frameRef.current = requestAnimationFrame(animate);

    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
    };
  }, [targetValue, duration]);

  return displayValue;
};

export default useAnimatedCounter;
