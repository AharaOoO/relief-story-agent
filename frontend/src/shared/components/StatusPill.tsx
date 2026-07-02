import { cn } from "../utils/cn";

interface StatusPillProps {
  label: string;
  status?: "ready" | "running" | "warning" | "error" | "idle";
  className?: string;
}

const statusMap = {
  ready: "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]",
  running: "bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.5)]",
  warning: "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]",
  error: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]",
  idle: "bg-slate-400",
};

export function StatusPill({ label, status = "idle", className }: StatusPillProps) {
  return (
    <span
      className={cn(
        "liquid-pill inline-flex items-center gap-2 px-3 py-1.5 text-xs font-semibold text-slate-600",
        className
      )}
    >
      <span className={cn("h-2.5 w-2.5 rounded-full", statusMap[status])} />
      {label}
    </span>
  );
}
