import { Download, CheckCircle2 } from "lucide-react";
import { getDownloadUrl } from "@/lib/api";

interface DownloadViewProps {
  jobId: string;
  onReset: () => void;
}

const DownloadView = ({ jobId, onReset }: DownloadViewProps) => (
  <div className="w-full max-w-md mx-auto text-center space-y-8">
    <div className="flex justify-center">
      <div className="rounded-full bg-success/10 p-6">
        <CheckCircle2 className="h-16 w-16 text-success" />
      </div>
    </div>

    <div className="space-y-2">
      <h1 className="text-3xl font-bold tracking-tight">Book Ready</h1>
      <p className="text-muted-foreground text-sm">
        Your generated PDF is ready to download.
      </p>
    </div>

    <a
      href={getDownloadUrl(jobId)}
      className="inline-flex items-center gap-2 rounded-md bg-primary text-primary-foreground px-8 py-3 font-semibold text-sm
        hover:brightness-110 transition-all glow-primary hover:glow-primary-strong"
    >
      <Download className="h-4 w-4" />
      Download PDF
    </a>

    <button
      onClick={onReset}
      className="block mx-auto text-sm text-muted-foreground hover:text-foreground transition"
    >
      Generate another book
    </button>
  </div>
);

export default DownloadView;
