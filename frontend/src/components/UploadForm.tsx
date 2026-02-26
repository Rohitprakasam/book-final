import { useState, useRef, type DragEvent } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import type { GenerateConfig } from "@/lib/api";
import logo from "@/assets/logo.png";

interface UploadFormProps {
  onSubmit: (file: File, config: GenerateConfig) => void;
  isLoading: boolean;
}

const UploadForm = ({ onSubmit, isLoading }: UploadFormProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [subject, setSubject] = useState("");
  const [persona, setPersona] = useState("");
  const [academicLevel, setAcademicLevel] = useState("Undergraduate");
  const [pages, setPages] = useState(300);
  const [maxDiagrams, setMaxDiagrams] = useState(40);
  const [skipImages, setSkipImages] = useState(false);
  const [provider, setProvider] = useState<"gemini" | "ollama">("gemini");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith(".pdf") || dropped.name.endsWith(".txt"))) {
      setFile(dropped);
    }
  };

  const handleSubmit = () => {
    if (!file || !subject.trim() || !persona.trim()) return;
    
    // Add new fields to the object. (Note: GenerateConfig type needs update in api.ts)
    onSubmit(file, {
      book_subject: subject,
      book_persona: persona,
      academic_level: academicLevel,
      target_pages: pages,
      max_new_diagrams: skipImages ? 0 : maxDiagrams,
      skip_images: skipImages,
      provider: provider,
      ollama_url: ollamaUrl,
    } as any);
  };

  return (
    <div className="w-full max-w-2xl mx-auto space-y-8">
      <div className="text-center space-y-4">
        <img src={logo} alt="UEducate logo" className="h-10 mx-auto" />
        <h1 className="text-4xl font-bold tracking-tight">
          Book<span className="text-primary">Educate</span>
        </h1>
        <p className="text-muted-foreground">
          Upload your source material and configure generation settings.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative cursor-pointer rounded-lg border-2 border-dashed p-12
          flex flex-col items-center gap-3 transition-all duration-200
          ${dragOver
            ? "border-primary bg-primary/5 glow-primary"
            : file
              ? "border-success/50 bg-success/5"
              : "border-border hover:border-muted-foreground/40 bg-card"
          }
        `}
      >
        {file ? (
          <>
            <FileText className="h-10 w-10 text-success" />
            <p className="text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">
              {(file.size / 1024 / 1024).toFixed(2)} MB — Click to change
            </p>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Drop a <span className="text-foreground font-medium">.pdf</span> or{" "}
              <span className="text-foreground font-medium">.txt</span> file here, or click to browse
            </p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
        />
      </div>

      {/* Config Sections */}
      <div className="space-y-6">
        
        {/* Section 1: Book Details */}
        <div className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs text-primary">1</span>
            Book Details
          </h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-1.5 sm:col-span-2">
              <label className="text-sm font-medium text-muted-foreground">Book Subject</label>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g. General Engineering"
                className="w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted-foreground">Author Persona</label>
              <input
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                placeholder="e.g. Senior Engineering Professor"
                className="w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted-foreground">Academic Level</label>
              <select
                value={academicLevel}
                onChange={(e) => setAcademicLevel(e.target.value)}
                className="w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition"
              >
                <option value="Undergraduate">Undergraduate</option>
                <option value="Graduate">Graduate</option>
                <option value="Research">Research / PhD</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Document Scope */}
        <div className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs text-primary">2</span>
            Document Scope
          </h3>
          <div className="grid sm:grid-cols-2 gap-6">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted-foreground flex justify-between">
                <span>Target Pages</span>
                <span className="text-foreground font-mono">{pages}</span>
              </label>
              <input
                type="range"
                min={50}
                max={1200}
                step={50}
                value={pages}
                onChange={(e) => setPages(Number(e.target.value))}
                className="w-full accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>50</span><span>1200</span>
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted-foreground flex justify-between">
                <span>Max AI Diagrams</span>
                <span className="text-foreground font-mono">{maxDiagrams}</span>
              </label>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={maxDiagrams}
                onChange={(e) => setMaxDiagrams(Number(e.target.value))}
                disabled={skipImages}
                className={`w-full accent-primary ${skipImages ? 'opacity-50 cursor-not-allowed' : ''}`}
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0</span><span>100</span>
              </div>
            </div>
            <div className="sm:col-span-2">
              <div className="flex items-center justify-between rounded-md border border-border bg-secondary px-4 py-3">
                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-foreground">Placeholders Only</p>
                  <p className="text-xs text-muted-foreground">
                    Skip AI image generation entirely & use colorful placeholder boxes instead. Much faster.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={skipImages}
                  onClick={() => setSkipImages(!skipImages)}
                  className={`
                    relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent
                    transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/40
                    ${skipImages ? "bg-primary" : "bg-muted-foreground/30"}
                  `}
                >
                  <span
                    className={`
                      pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg
                      transform transition duration-200 ease-in-out
                      ${skipImages ? "translate-x-5" : "translate-x-0"}
                    `}
                  />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: AI Configuration */}
        <div className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs text-primary">3</span>
            AI Configuration
          </h3>
          <div className="grid gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-muted-foreground">AI Provider</label>
              <div className="flex rounded-md border border-border overflow-hidden">
                <button
                  type="button"
                  onClick={() => setProvider("gemini")}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                    provider === "gemini" 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-secondary text-foreground hover:bg-muted-foreground/10"
                  }`}
                >
                  Cloud (Gemini API)
                </button>
                <button
                  type="button"
                  onClick={() => setProvider("ollama")}
                  className={`flex-1 py-2.5 text-sm font-medium transition-colors border-l border-border ${
                    provider === "ollama" 
                      ? "bg-primary text-primary-foreground" 
                      : "bg-secondary text-foreground hover:bg-muted-foreground/10"
                  }`}
                >
                  Local Network (Ollama)
                </button>
              </div>
            </div>
            
            {provider === "ollama" && (
              <div className="space-y-1.5 slide-in-from-top-2 animate-in duration-200">
                <label className="text-sm font-medium text-muted-foreground">Ollama API URL</label>
                <input
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 transition"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Enter your neighbor's or local Ollama IP address. E.g., http://192.168.1.50:11434
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <button
        onClick={handleSubmit}
        disabled={!file || !subject.trim() || !persona.trim() || isLoading}
        className="w-full rounded-md bg-primary text-primary-foreground py-3 font-semibold text-sm
          hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed
          transition-all glow-primary hover:glow-primary-strong flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Submitting…
          </>
        ) : (
          "Generate Book"
        )}
      </button>
    </div>
  );
};

export default UploadForm;
