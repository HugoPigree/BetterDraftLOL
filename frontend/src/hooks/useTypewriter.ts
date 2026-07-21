import { useCallback, useEffect, useState } from "react";

export function useTypewriter(text: string, speedMs = 26) {
  const [displayed, setDisplayed] = useState("");
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    setDisplayed("");
    setIsComplete(false);

    if (!text) {
      setIsComplete(true);
      return;
    }

    let index = 0;
    const timer = window.setInterval(() => {
      index += 1;
      setDisplayed(text.slice(0, index));
      if (index >= text.length) {
        window.clearInterval(timer);
        setIsComplete(true);
      }
    }, speedMs);

    return () => window.clearInterval(timer);
  }, [text, speedMs]);

  const skip = useCallback(() => {
    setDisplayed(text);
    setIsComplete(true);
  }, [text]);

  return { displayed, isComplete, skip };
}
