import { useEffect, useRef } from "react";

export function OceanVideoBackground() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        video.pause();
        return;
      }
      const result = video.play();
      result?.catch?.(() => {
        // Autoplay may be blocked; the poster/background remains visible.
      });
    }
  }, []);

  return (
    <>
      <div className="ocean-video-layer">
        <video
          ref={videoRef}
          src="/beach_bg.mp4"
          poster="/beach-poster.webp"
          autoPlay
          muted
          loop
          playsInline
        />
      </div>
      <div className="ocean-video-overlay" />
      <div className="ocean-noise" />
    </>
  );
}
