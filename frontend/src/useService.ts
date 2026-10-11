import { useCallback, useEffect, useRef, useState } from "react";

type Status = "checking" | "online" | "offline";
export function useService() {
  const [status, setStatus] = useState<Status>("checking");
  const [modelReady, setModelReady] = useState(false);
  const [reconnects, setReconnects] = useState(0);
  const current = useRef<Status>("checking");
  const mounted = useRef(true);
  const inflight = useRef(false);
  const check = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const response = await fetch("/api/health", {
        signal: AbortSignal.timeout(4000),
        cache: "no-store",
      });
      if (!response.ok) throw Error("offline");
      const value = await response.json();
      if (value.service !== "scholartrace") throw Error("unexpected service");
      if (!mounted.current) return;
      if (current.current === "offline") setReconnects((v) => v + 1);
      current.current = "online";
      setStatus("online");
      setModelReady(value.model_available);
    } catch {
      if (mounted.current) {
        current.current = "offline";
        setStatus("offline");
        setModelReady(false);
      }
    } finally {
      inflight.current = false;
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void check();
    const timer = setInterval(() => void check(), 5000);
    window.addEventListener("focus", check);
    return () => {
      mounted.current = false;
      clearInterval(timer);
      window.removeEventListener("focus", check);
    };
  }, [check]);
  return { status, modelReady, reconnects, check };
}
