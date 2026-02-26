import { useState } from "react";
import { useNavigate } from "react-router-dom";
import UploadForm from "@/components/UploadForm";
import { submitJob, type GenerateConfig } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";

export default function CreateJob() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = async (file: File, config: GenerateConfig) => {
    setIsSubmitting(true);
    try {
      const res = await submitJob(file, config);
      // Automatically route to the Job Status page upon successful upload
      navigate(`/job/${res.job_id}`);
    } catch (err: any) {
      console.error("Upload failed", err);
      toast({
        title: "Upload Failed",
        description: err?.message || "An error occurred while uploading your document.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold tracking-tight mb-2">Create New Book</h1>
        <p className="text-muted-foreground">Configure your pipeline settings and upload your source material.</p>
      </div>
      
      <div className="bg-background">
        <UploadForm onSubmit={handleSubmit} isLoading={isSubmitting} />
      </div>
    </div>
  );
}
