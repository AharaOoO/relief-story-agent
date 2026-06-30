import React from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "../utils/cn";

export interface LiquidShinyButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  className?: string;
  showArrow?: boolean;
}

export const LiquidShinyButton = React.forwardRef<HTMLButtonElement, LiquidShinyButtonProps>(
  ({ children, className, showArrow = true, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        className={cn("liquid-shiny-button", className)}
        {...props}
      >
        <span className="relative z-10">{children}</span>

        {showArrow && (
          <span className="relative z-10 grid h-7 w-7 place-items-center rounded-full bg-white/60 text-blue-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.95),0_4px_12px_rgba(88,122,190,0.15)] transition duration-200">
            <ArrowRight size={15} />
          </span>
        )}
      </button>
    );
  }
);

LiquidShinyButton.displayName = "LiquidShinyButton";
