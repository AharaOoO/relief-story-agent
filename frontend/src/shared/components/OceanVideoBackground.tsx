import { useEffect, useRef } from "react";

export function OceanVideoBackground() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      video.play().catch(() => {
        // Autoplay may be blocked by some browsers initially
      });
    }
  }, []);

  return (
    <>
      <div className="ocean-video-layer">
        <video
          ref={videoRef}
          src="/beach_bg.mp4"
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
