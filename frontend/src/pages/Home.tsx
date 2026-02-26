import { Link } from "react-router-dom";
import { BookOpen, Zap, Layers, Image as ImageIcon } from "lucide-react";
import logo from "@/assets/logo.png";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] text-center space-y-12">
      <div className="space-y-6 max-w-3xl">
        <img src={logo} alt="BookEducate Logo" className="h-20 w-auto object-contain mx-auto drop-shadow-md" />
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight">
          Book<span className="text-primary">Educate</span>
        </h1>
        <p className="text-xl md:text-2xl text-muted-foreground leading-relaxed">
          Transform raw PDF syllabi and documents into publication-ready, beautifully structured textbooks in seconds using advanced AI swarm intelligence.
        </p>
      </div>

      <div className="flex gap-4">
        <Link 
          to="/create" 
          className="inline-flex h-12 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 hover:scale-105 active:scale-95 duration-200 glow-primary"
        >
          Start Generating
        </Link>
        <Link 
          to="/history" 
          className="inline-flex h-12 items-center justify-center rounded-md border border-input bg-background px-8 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground hover:scale-105 active:scale-95 duration-200"
        >
          View Past Books
        </Link>
      </div>

      <div className="grid sm:grid-cols-3 gap-8 pt-12 mt-8 border-t border-border/50 max-w-5xl">
        <div className="flex flex-col items-center space-y-3 text-center p-4">
          <div className="p-3 bg-primary/10 rounded-full text-primary">
            <Zap className="h-6 w-6" />
          </div>
          <h3 className="text-lg font-semibold">Lightning Fast Typst Engine</h3>
          <p className="text-sm text-muted-foreground">Compiles completely structured, mathematically rigorous PDFs in under a minute without LaTeX crashing.</p>
        </div>
        <div className="flex flex-col items-center space-y-3 text-center p-4">
          <div className="p-3 bg-primary/10 rounded-full text-primary">
            <Layers className="h-6 w-6" />
          </div>
          <h3 className="text-lg font-semibold">Local Ollama Support</h3>
          <p className="text-sm text-muted-foreground">Seamlessly toggle between Google Gemini Cloud APIs or secure, local-network Ollama instances.</p>
        </div>
        <div className="flex flex-col items-center space-y-3 text-center p-4">
          <div className="p-3 bg-primary/10 rounded-full text-primary">
            <ImageIcon className="h-6 w-6" />
          </div>
          <h3 className="text-lg font-semibold">Smart Image Placeholders</h3>
          <p className="text-sm text-muted-foreground">Skip costly image generation and use colorful semantic placeholders when prototyping textbook layouts.</p>
        </div>
      </div>
    </div>
  );
}
