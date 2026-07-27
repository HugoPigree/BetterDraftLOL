import { useEffect, useRef, useState } from "react";

interface UseDraftTurnTimerOptions {
  enabled: boolean;
  isPlayerTurn: boolean;
  seconds: number;
  onExpire: () => void;
}

export function useDraftTurnTimer({
  enabled,
  isPlayerTurn,
  seconds,
  onExpire,
}: UseDraftTurnTimerOptions) {
  const [remaining, setRemaining] = useState(seconds);
  const expiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    if (!enabled || !isPlayerTurn) {
      setRemaining(seconds);
      expiredRef.current = false;
      return;
    }

    setRemaining(seconds);
    expiredRef.current = false;

    const interval = window.setInterval(() => {
      setRemaining((current) => {
        if (current <= 1) {
          window.clearInterval(interval);
          if (!expiredRef.current) {
            expiredRef.current = true;
            onExpireRef.current();
          }
          return 0;
        }
        return current - 1;
      });
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [enabled, isPlayerTurn, seconds]);

  return { remaining, urgent: remaining <= 3 && isPlayerTurn && enabled };
}
