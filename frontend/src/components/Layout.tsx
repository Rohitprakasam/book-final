import { Outlet, Link, useLocation } from "react-router-dom";
import { BookOpen, History, PlusCircle } from "lucide-react";
import logo from "@/assets/logo.png";

export default function Layout() {
  const location = useLocation();

  const navItems = [
    { path: "/", label: "Home", icon: BookOpen },
    { path: "/create", label: "Create Book", icon: PlusCircle },
    { path: "/history", label: "History", icon: History },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Subtle background grid */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03] z-0"
        style={{
          backgroundImage:
            "linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center mx-auto px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2 mr-6">
            <img src={logo} alt="BookEducate logo" className="h-8 w-auto object-contain" />
            <span className="hidden font-bold sm:inline-block">BookEducate</span>
          </Link>

          <nav className="flex items-center gap-6 text-sm font-medium">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path || 
                              (item.path !== "/" && location.pathname.startsWith(item.path));
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 transition-colors hover:text-foreground/80 ${
                    isActive ? "text-foreground" : "text-foreground/60"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden sm:inline-block">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 relative z-10 w-full container mx-auto p-4 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}
