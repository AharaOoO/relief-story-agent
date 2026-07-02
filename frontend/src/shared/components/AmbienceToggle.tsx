import { useEffect, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";
import { cn } from "../utils/cn"; // Wait, does the project have a cn utility? Let's check where standard cn is.

export interface AmbienceToggleProps {
  oceanSrc: string;
  className?: string;
}

export function AmbienceToggle({ oceanSrc, className }: AmbienceToggleProps) {
  const [enabled, setEnabled] = useState(false);
  const oceanRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!oceanRef.current) return;

    if (enabled) {
      oceanRef.current.volume = 0.28;
      oceanRef.current.loop = true;
      oceanRef.current.play().catch(() => setEnabled(false));
    } else {
      oceanRef.current.pause();
    }
  }, [enabled]);

  return (
    <button
      type="button"
      onClick={() => setEnabled((v) => !v)}
      className={cn(
        "liquid-pill relative z-10 inline-flex items-center gap-2 px-4 py-2 text-sm text-slate-600 transition hover:scale-[1.03]",
        className
      )}
      aria-pressed={enabled}
    >
      {enabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
      {enabled ? "白噪音：开" : "白噪音：关"}
      <audio ref={oceanRef} src={oceanSrc} preload="none" />
    </button>
  );
}
