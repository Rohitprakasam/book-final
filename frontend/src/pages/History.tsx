import { useEffect, useState } from "react";
import { History as HistoryIcon, Play, AlertCircle, CheckCircle2, Loader2, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { listJobs, type ProgressData } from "@/lib/api";

export default function History() {
  const [jobs, setJobs] = useState<ProgressData[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await listJobs();
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
      case "completed": return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case "failed": return <AlertCircle className="h-5 w-5 text-destructive" />;
      case "processing": return <Loader2 className="h-5 w-5 text-primary animate-spin" />;
      default: return <Play className="h-5 w-5 text-muted-foreground" />;
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="mb-8 flex items-center gap-3">
        <div className="p-3 bg-primary/10 rounded-lg text-primary">
          <HistoryIcon className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Generation History</h1>
          <p className="text-muted-foreground">View your past books and resume incomplete jobs.</p>
        </div>
      </div>

      <div className="bg-card border rounded-xl shadow-sm overflow-hidden min-h-[50vh]">
        {loading ? (
          <div className="flex flex-col items-center justify-center p-20 text-muted-foreground gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p>Loading history...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-20 text-muted-foreground">
            <p>No recent jobs found.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {jobs.map((job) => (
              <button
                key={job.job_id}
                onClick={() => navigate(`/job/${job.job_id}`)}
                className="w-full text-left p-6 hover:bg-muted/50 transition-colors flex items-center justify-between group"
              >
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-full bg-background border group-hover:border-primary/50 transition-colors">
                    {getStatusIcon(job.status)}
                  </div>
                  <div>
                    <div className="font-mono text-sm font-bold flex items-center gap-3 mb-1">
                      {job.job_id}
                      {job.status === "failed" && job.is_recoverable && (
                        <span className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded uppercase tracking-wider font-sans">
                          Resumable
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground max-w-[400px] truncate">
                      {job.message || "Processing started..."}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <div className="text-sm font-bold">{Math.round(job.progress_percentage)}%</div>
                    <div className="text-[10px] uppercase text-muted-foreground tracking-widest">{job.status}</div>
                  </div>
                  <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors group-hover:translate-x-1 duration-300" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
