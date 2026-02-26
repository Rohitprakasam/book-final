import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ProgressView from "@/components/ProgressView";
import DownloadView from "@/components/DownloadView";
import ErrorView from "@/components/ErrorView";
import { Loader2, ArrowLeft } from "lucide-react";
import { resumeJob, type ProgressData } from "@/lib/api";

type Stage = "loading" | "progress" | "done" | "error";

export default function JobDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const [stage, setStage] = useState<Stage>("loading");
  const [error, setError] = useState<ProgressData["error"]>(undefined);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!id) {
      navigate("/");
      return;
    }
    
    // Fetch initial status
    fetch(`http://localhost:8000/api/v1/jobs/${id}`)
      .then(res => {
        if (!res.ok) throw new Error("Not found");
        return res.json();
      })
      .then((data: ProgressData) => {
        if (data.status === "completed") {
          setStage("done");
        } else if (data.status === "failed") {
          setError(data.error || {
             code: "UNKNOWN_ERROR",
             phase_failed_in: data.current_phase?.toString() || "Pipeline",
             message: data.message || "An unknown error occurred.",
             is_recoverable: data.is_recoverable ?? true,
          });
          setStage("error");
        } else {
          setStage("progress");
        }
      })
      .catch(() => {
        setError({
          code: "NOT_FOUND",
          phase_failed_in: "Network",
          message: "Job not found or server unreachable.",
          is_recoverable: false,
        });
        setStage("error");
      });
  }, [id, navigate]);

  const handleComplete = useCallback(() => setStage("done"), []);
  
  const handleError = useCallback((e: ProgressData["error"]) => {
    setError(e);
    setStage("error");
  }, []);

  const handleReset = useCallback(() => {
    navigate("/create");
  }, [navigate]);

  const handleResume = async () => {
    if (!id) return;
    setIsSubmitting(true);
    try {
      const phase = error?.resume_phase || 1; 
      await resumeJob(id, phase); 
      setError(undefined);
      setStage("progress");
    } catch (err: any) {
      console.error("Resume failed", err);
      setError({
        code: "RESUME_ERROR",
        phase_failed_in: "Resume",
        message: err?.message ?? "Failed to resume job.",
        is_recoverable: true,
        resume_phase: error?.resume_phase, 
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (stage === "loading" || isSubmitting) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-muted-foreground gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p>{isSubmitting ? "Resuming job..." : "Loading job details..."}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8">
      <button 
        onClick={() => navigate("/history")}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-8 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to History
      </button>

      {stage === "progress" && id && (
        <ProgressView jobId={id} onComplete={handleComplete} onError={handleError} />
      )}
      {stage === "done" && id && (
        <DownloadView jobId={id} onReset={handleReset} />
      )}
      {stage === "error" && error && (
        <ErrorView error={error} onReset={handleReset} onResume={handleResume} />
      )}
    </div>
  );
}
