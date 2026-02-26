import { useState, useCallback, useEffect } from "react";
import UploadForm from "@/components/UploadForm";
import ProgressView from "@/components/ProgressView";
import DownloadView from "@/components/DownloadView";
import ErrorView from "@/components/ErrorView";
import JobsList from "@/components/JobsList";
import { History, Loader2 } from "lucide-react";
import { submitJob, resumeJob, type GenerateConfig, type ProgressData } from "@/lib/api";

type Stage = "upload" | "progress" | "done" | "error";

const Index = () => {
  const [stage, setStage] = useState<Stage>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("book_stage") as Stage) || "upload";
    }
    return "upload";
  });
  const [jobId, setJobId] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("book_jobId") || "";
    }
    return "";
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<ProgressData["error"]>(undefined);
  const [showHistory, setShowHistory] = useState(false);

  // Persist state changes
  useEffect(() => {
    localStorage.setItem("book_stage", stage);
    localStorage.setItem("book_jobId", jobId);
  }, [stage, jobId]);

  // Restore error state if refreshed while in error stage
  useEffect(() => {
    if (stage === "error" && !error && jobId) {
      fetch(`http://localhost:3030/api/v1/jobs/${jobId}`)
        .then(res => res.json())
        .then(data => {
          if (data.error) {
            setError(data.error);
          } else {
            // Fallback generic error if backend doesn't provide one
            setError({
              code: "UNKNOWN_ERROR",
              phase_failed_in: data.current_phase || "Pipeline",
              message: data.message || "An unknown error occurred.",
              is_recoverable: data.is_recoverable ?? true,
            });
          }
        })
        .catch(err => {
          console.error("Failed to recover error state", err);
          setError({
            code: "NETWORK_ERROR",
            phase_failed_in: "Network",
            message: "Failed to connect to backend.",
            is_recoverable: true,
          });
        });
    }
  }, [stage, error, jobId]);

  const handleSubmit = async (file: File, config: GenerateConfig) => {
    setIsSubmitting(true);
    try {
      const res = await submitJob(file, config);
      setJobId(res.job_id);
      setStage("progress");
    } catch (err: any) {
      console.error("Upload failed", err);
      setError({
        code: err?.error_code ?? "UPLOAD_ERROR",
        phase_failed_in: "Upload",
        message: err?.message ?? "Failed to submit job.",
        is_recoverable: true,
      });
      setStage("error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResume = async () => {
    if (!jobId) return;
    setIsSubmitting(true);
    try {
      // Prioritize the backend's resume_phase if available
      const phase = error?.resume_phase || 1; 
      await resumeJob(jobId, phase); 
      
      // Clear error immediately on trigger to show progress view
      setError(undefined);
      setStage("progress");
    } catch (err: any) {
      console.error("Resume failed", err);
      setError({
        code: "RESUME_ERROR",
        phase_failed_in: "Resume",
        message: err?.message ?? "Failed to resume job.",
        is_recoverable: true,
        resume_phase: error?.resume_phase, // Persist previous resume phase
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleComplete = useCallback(() => setStage("done"), []);
  const handleError = useCallback((e: ProgressData["error"]) => {
    setError(e);
    setStage("error");
  }, []);

  const reset = () => {
    setStage("upload");
    setJobId("");
    setError(undefined);
    localStorage.removeItem("book_stage");
    localStorage.removeItem("book_jobId");
  };

  const handleSelectJob = async (id: string, status: string) => {
    setJobId(id);
    if (status === "completed") {
      setStage("done");
      setError(undefined);
    } else if (status === "failed") {
      // Fetch full job to get recovery info
      try {
        const res = await fetch(`http://localhost:3030/api/v1/jobs/${id}`);
        const data = await res.json();
        setError(data.error);
        setStage("error");
      } catch (err) {
        setStage("error");
      }
    } else {
      setStage("progress");
      setError(undefined);
    }
    setShowHistory(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      {/* History Button */}
      <button
        onClick={() => setShowHistory(true)}
        className="fixed top-6 right-6 z-50 p-3 rounded-full bg-card border shadow-lg hover:bg-muted transition-all active:scale-95 group"
        title="View Recent Jobs"
      >
        <History className="h-5 w-5 text-primary group-hover:rotate-12 transition-transform" />
      </button>

      {showHistory && (
        <JobsList onSelect={handleSelectJob} onClose={() => setShowHistory(false)} />
      )}
      {/* Subtle grid background */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative z-10 w-full">
        {stage === "upload" && <UploadForm onSubmit={handleSubmit} isLoading={isSubmitting} />}
        {stage === "progress" && (
          <ProgressView jobId={jobId} onComplete={handleComplete} onError={handleError} />
        )}
        {stage === "done" && <DownloadView jobId={jobId} onReset={reset} />}
        {stage === "error" && !error && (
          <div className="flex flex-col items-center justify-center p-12 text-muted-foreground gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p>Recovering job state...</p>
          </div>
        )}
        {stage === "error" && error && (
          <ErrorView error={error} onReset={reset} onResume={handleResume} />
        )}
      </div>
    </div>
  );
};

export default Index;
