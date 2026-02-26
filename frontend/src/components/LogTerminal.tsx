import { useEffect, useRef, useState } from "react";
import { Terminal } from "lucide-react";
import { fetchLogs, type LogEntry } from "@/lib/api";

interface LogTerminalProps {
  jobId: string;
  isActive: boolean;
}

const levelColor: Record<string, string> = {
  INFO: "text-primary",
  WARN: "text-warning",
  ERROR: "text-destructive",
  DEBUG: "text-muted-foreground",
};

const LogTerminal = ({ jobId, isActive }: LogTerminalProps) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const cursorRef = useRef<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // If not active, do nothing. 'processing' is the backend status for active runs.
    if (!isActive) return;
    let active = true;

    const poll = async () => {
      try {
        const res = await fetchLogs(jobId, cursorRef.current);
        if (!active) return;
        if (res.logs.length > 0) {
          setLogs((prev) => [...prev, ...res.logs]);
          cursorRef.current = res.next_cursor ?? undefined;
        }
      } catch {
        /* silent */
      }
      if (active) setTimeout(poll, 3000);
    };

    poll();
    return () => {
      active = false;
    };
  }, [jobId, isActive]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-secondary/50">
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs font-mono text-muted-foreground">
          Agent Logs
        </span>
        {isActive && (
          <span className="ml-auto h-2 w-2 rounded-full bg-success animate-pulse-glow" />
        )}
      </div>
      <div className="h-56 overflow-y-auto p-4 font-mono text-xs leading-relaxed terminal-scrollbar">
        {logs.length === 0 && (
          <p className="text-muted-foreground">Waiting for agent output…</p>
        )}
        {logs.map((log, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-muted-foreground shrink-0">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span
              className={`shrink-0 ${levelColor[log.level] ?? "text-foreground"}`}
            >
              [{log.level}]
            </span>
            <span className="text-muted-foreground shrink-0">
              {log.source}:
            </span>
            <span className="text-foreground">{log.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default LogTerminal;
