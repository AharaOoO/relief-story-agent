import { Sparkles, Activity } from "lucide-react";
import { cn } from "../utils/cn";

export interface NavItem {
  id: string;
  label: string;
}

interface FloatingNavProps {
  items: NavItem[];
  activeId?: string;
  onNavigate?: (id: string) => void;
}

export function FloatingNav({ items, activeId, onNavigate }: FloatingNavProps) {
  const handleClick = (id: string) => {
    onNavigate?.(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className="fixed left-0 right-0 top-6 z-50 flex justify-center px-4">
      <nav className="liquid-pill flex h-[72px] w-full max-w-[1120px] items-center justify-between px-5 md:px-8">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-[#b7d6ff] to-[#4c8dff] shadow-[0_8px_24px_rgba(88,135,255,0.35)]">
            <Sparkles size={19} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight text-slate-800">Relief Story Agent</div>
            <div className="text-[10px] uppercase tracking-[0.22em] text-slate-400">Ocean Liquid Workbench</div>
          </div>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => handleClick(item.id)}
              className={cn(
                "relative rounded-full px-4 py-2 text-sm transition font-medium",
                activeId === item.id
                  ? "bg-white/55 text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.82)]"
                  : "text-slate-500 hover:bg-white/35 hover:text-slate-900"
              )}
            >
              {item.label}
              {activeId === item.id ? (
                <span className="absolute -bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-blue-500 shadow-[0_0_12px_rgba(80,130,255,0.8)]" />
              ) : null}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 rounded-full bg-white/30 px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
          <span className="text-xs font-semibold text-slate-600 flex items-center gap-1.5">
            <Activity size={12} className="text-emerald-500 animate-pulse" />
            V2 RUNTIME ACTIVE
          </span>
        </div>
      </nav>
    </header>
  );
}
