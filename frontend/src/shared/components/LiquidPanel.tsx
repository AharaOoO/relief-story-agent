import React from "react";
import { cn } from "../utils/cn";

interface LiquidPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  variant?: "panel" | "card" | "pill";
}

export function LiquidPanel({ children, className, variant = "panel", ...props }: LiquidPanelProps) {
  return (
    <div
      className={cn(
        "liquid-glass",
        variant === "panel" && "liquid-panel p-6 md:p-8",
        variant === "card" && "liquid-card p-5 md:p-6",
        variant === "pill" && "liquid-pill px-5 py-3",
        className
      )}
      {...props}
    >
      <div className="relative z-10">{children}</div>
    </div>
  );
}
