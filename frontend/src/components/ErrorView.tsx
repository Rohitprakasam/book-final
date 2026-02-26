import { XCircle } from "lucide-react";
import type { ProgressData } from "@/lib/api";

interface ErrorViewProps {
  error: NonNullable<ProgressData["error"]>;
  onReset: () => void;
  onResume: () => void;
}

const ErrorView = ({ error, onReset, onResume }: ErrorViewProps) => (
  <div className="w-full max-w-md mx-auto text-center space-y-8">
    <div className="flex justify-center">
      <div className="rounded-full bg-destructive/10 p-6">
        <XCircle className="h-16 w-16 text-destructive" />
      </div>
    </div>

    <div className="space-y-2">
      <h1 className="text-3xl font-bold tracking-tight">Generation Failed</h1>
      <p className="text-sm text-muted-foreground">{error.phase_failed_in}</p>
    </div>

    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-left space-y-2">
      <p className="text-sm font-mono text-destructive">{error.code}</p>
      <p className="text-sm text-foreground">{error.message}</p>
      {!error.is_recoverable && (
        <p className="text-xs text-muted-foreground">This error is not recoverable.</p>
      )}
    </div>

    <div className="flex flex-col gap-3">
      {error.is_recoverable && (
        <button
          onClick={onResume}
          className="rounded-md bg-primary text-primary-foreground px-8 py-3 font-semibold text-sm hover:bg-primary/90 transition shadow-lg shadow-primary/20"
        >
          Resume Generation
          <span className="block text-[10px] opacity-70 font-normal uppercase mt-0.5">
            Will resume from {error.resume_phase ? `Phase ${error.resume_phase}` : 'start'}
          </span>
        </button>
      )}
      <button
        onClick={onReset}
        className="rounded-md bg-secondary text-secondary-foreground px-8 py-3 font-semibold text-sm hover:bg-secondary/80 transition"
      >
        {error.is_recoverable ? "Cancel & Start Over" : "Start Over"}
      </button>
    </div>
  </div>
);

export default ErrorView;
