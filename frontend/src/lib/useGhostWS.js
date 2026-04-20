import { useEffect, useRef } from "react";
import { wsUrl } from "./ghostApi";

export function useGhostWS(onEvent) {
  const ref = useRef(null);
  useEffect(() => {
    let retry;
    const connect = () => {
      const ws = new WebSocket(wsUrl());
      ref.current = ws;
      ws.onmessage = (m) => {
        try {
          const { event, data } = JSON.parse(m.data);
          onEvent(event, data);
        } catch {}
      };
      ws.onclose = () => {
        retry = setTimeout(connect, 2500);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      clearTimeout(retry);
      try {
        ref.current?.close();
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
