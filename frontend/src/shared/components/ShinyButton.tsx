import React from "react";
import { cn } from "../utils/cn";

export interface ShinyButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  className?: string;
}

export const ShinyButton = React.forwardRef<HTMLButtonElement, ShinyButtonProps>(
  ({ children, className, ...props }, ref) => {
    return (
      <button
        ref={ref}
        type="button"
        className={cn("shiny-button", className)}
        {...props}
      >
        {children}
      </button>
    );
  }
);

ShinyButton.displayName = "ShinyButton";
