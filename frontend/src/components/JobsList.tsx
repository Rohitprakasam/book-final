import { useEffect, useState } from "react";
import { History, Play, AlertCircle, CheckCircle2, Loader2, ArrowRight } from "lucide-react";
import { listJobs, type ProgressData } from "@/lib/api";

interface JobsListProps {
  onSelect: (jobId: string, status: string) => void;
  onClose: () => void;
}

const JobsList = ({ onSelect, onClose }: JobsListProps) => {
  const [jobs, setJobs] = useState<ProgressData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await listJobs();
        // Sort by created_at desc
        const sorted = (res.jobs || []).sort((a: any, b: any) => b.created_at - a.created_at);
        setJobs(sorted);
      } catch (err) {
        console.error("Failed to fetch jobs", err);
      } finally {
        setLoading(false);
      }
    };
    fetchJobs();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "failed": return <AlertCircle className="h-4 w-4 text-destructive" />;
      case "processing": return <Loader2 className="h-4 w-4 text-primary animate-spin" />;
      default: return <Play className="h-4 w-4 text-muted-foreground" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-card border rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
        <div className="p-4 border-b flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-primary" />
            <h2 className="font-bold">Recent Generations</h2>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {loading ? (
            <div className="p-8 text-center text-muted-foreground italic flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin" />
              Loading history...
            </div>
          ) : jobs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground italic">
              No recent jobs found.
            </div>
          ) : (
            <div className="space-y-1">
              {jobs.map((job) => (
                <button
                  key={job.job_id}
                  onClick={() => onSelect(job.job_id, job.status)}
                  className="w-full text-left p-3 rounded-lg hover:bg-muted/50 border border-transparent hover:border-border transition-all flex items-center justify-between group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-md bg-muted group-hover:bg-background transition-colors">
                      {getStatusIcon(job.status)}
                    </div>
                    <div>
                      <div className="font-mono text-sm font-bold flex items-center gap-2">
                        {job.job_id}
                        {job.status === "failed" && job.is_recoverable && (
                          <span className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded uppercase tracking-wider">
                            Resumable
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground line-clamp-1 max-w-[250px]">
                        {job.message || "No activity yet"}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-xs font-bold">{Math.round(job.progress_percentage)}%</div>
                      <div className="text-[10px] uppercase text-muted-foreground tracking-tighter">{job.status}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity text-primary" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="p-4 border-t bg-muted/10 text-center">
          <p className="text-[10px] text-muted-foreground uppercase tracking-widest">
            BookUdecate V1.0 Dashboard
          </p>
        </div>
      </div>
    </div>
  );
};

export default JobsList;
