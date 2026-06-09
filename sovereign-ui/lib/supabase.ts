import { createClient, RealtimeChannel } from "@supabase/supabase-js";

const supabaseUrl  = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnon, {
  realtime: { params: { eventsPerSecond: 10 } },
});

// ── Type shapes matching the Supabase tables ────────────────────────────────

export interface TelemetryRow {
  id:           number;
  cpu:          number;   // 0–100
  temp:         number;   // celsius
  latency:      number;   // ms
  bandwidth:    number;   // Mbps
  active_nodes: number;
  inserted_at:  string;
}

export interface TranscriptRow {
  id:         number;
  speaker:    string;
  text:       string;
  inserted_at: string;
}

export interface UplinkLog {
  level:   "info" | "warn" | "error";
  message: string;
  ts:      string;
}

// ── Channel factories ───────────────────────────────────────────────────────

export function subscribeTelemetry(
  onRow: (row: TelemetryRow) => void
): RealtimeChannel {
  return supabase
    .channel("telemetry-live")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "telemetry" },
      (payload) => onRow(payload.new as TelemetryRow)
    )
    .subscribe();
}

export function subscribeTranscripts(
  onRow: (row: TranscriptRow) => void
): RealtimeChannel {
  return supabase
    .channel("transcripts-live")
    .on(
      "postgres_changes",
      { event: "INSERT", schema: "public", table: "transcripts" },
      (payload) => onRow(payload.new as TranscriptRow)
    )
    .subscribe();
}

export function subscribeUplinkLogs(
  onLog: (log: UplinkLog) => void
): RealtimeChannel {
  return supabase
    .channel("uplink-logs")
    .on("broadcast", { event: "new_log" }, (payload) =>
      onLog(payload.payload as UplinkLog)
    )
    .subscribe();
}
