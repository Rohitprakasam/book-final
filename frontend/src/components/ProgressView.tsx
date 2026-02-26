import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import CircularProgress from "./CircularProgress";
import LogTerminal from "./LogTerminal";
import { subscribeProgress, type ProgressData } from "@/lib/api";

interface ProgressViewProps {
  jobId: string;
  onComplete: () => void;
  onError: (error: ProgressData["error"]) => void;
}

const formatTime = (seconds: number | null | undefined) => {
  if (seconds == null || isNaN(seconds)) return "Calculating...";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m > 60) {
      const h = Math.floor(m / 60);
      const remainingM = m % 60;
      return `${h}h ${remainingM}m`;
  }
  return `${m}m ${s}s`;
};

const ProgressView = ({ jobId, onComplete, onError }: ProgressViewProps) => {
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [sseError, setSseError] = useState(false);

  useEffect(() => {
    const unsub = subscribeProgress(
      jobId,
      (data) => {
        setProgress(data);
        if (data.status === "completed") onComplete();
        if (data.status === "failed" && data.error) onError(data.error);
      },
      () => setSseError(true)
    );
    return unsub;
  }, [jobId, onComplete, onError]);

  return (
    <div className="w-full max-w-2xl mx-auto space-y-8 text-center">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Generating Your Book</h1>
        <p className="text-muted-foreground text-sm">
          Job <span className="font-mono text-foreground">{jobId}</span>
        </p>
      </div>

      <div className="flex justify-center">
        <CircularProgress percentage={progress?.progress_percentage ?? 0} />
      </div>

      <div className="flex flex-col sm:flex-row gap-4 justify-center items-center text-sm px-4 py-3 bg-secondary/50 rounded-lg max-w-sm mx-auto border border-border/50 backdrop-blur-sm">
          <div className="flex flex-col items-center flex-1">
              <span className="text-muted-foreground text-xs uppercase tracking-wider font-semibold mb-1">Phase ETA</span>
              <span className="font-mono text-primary font-medium">{formatTime(progress?.eta_phase_seconds)}</span>
          </div>
          <div className="w-px h-8 bg-border/50 hidden sm:block"></div>
          <div className="flex flex-col items-center flex-1">
              <span className="text-muted-foreground text-xs uppercase tracking-wider font-semibold mb-1">Total ETA</span>
              <span className="font-mono text-foreground font-medium">{formatTime(progress?.eta_total_seconds)}</span>
          </div>
      </div>

      <div className="space-y-1">
        <p className="text-sm font-semibold text-primary">
          {progress?.current_phase ?? "Initializing pipeline…"}
        </p>
        <p className="text-xs text-muted-foreground">
          {progress?.current_task ?? "Preparing agents…"}
        </p>
      </div>

      {sseError && (
        <div className="flex items-center justify-center gap-2 text-warning text-sm">
          <AlertTriangle className="h-4 w-4" />
          Connection lost — retrying…
        </div>
      )}

      <LogTerminal jobId={jobId} isActive={progress?.status === "running" || progress?.status === "processing" || !progress} />
    </div>
  );
};

export default ProgressView;
