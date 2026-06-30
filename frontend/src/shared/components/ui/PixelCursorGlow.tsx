import { useEffect, useState } from 'react'

export function PixelCursorGlow() {
  const [position, setPosition] = useState({ x: -1000, y: -1000 })

  useEffect(() => {
    let animationFrameId: number;
    let targetX = -1000;
    let targetY = -1000;
    let currentX = -1000;
    let currentY = -1000;

    const handleMouseMove = (e: MouseEvent) => {
      targetX = e.clientX;
      targetY = e.clientY;
    };

    const updatePosition = () => {
      // Smooth interpolation
      currentX += (targetX - currentX) * 0.15;
      currentY += (targetY - currentY) * 0.15;
      
      setPosition({ x: currentX, y: currentY });
      animationFrameId = requestAnimationFrame(updatePosition);
    };

    window.addEventListener('mousemove', handleMouseMove);
    updatePosition();

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, [])

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        pointerEvents: 'none',
        zIndex: 0, // Stay behind content
        overflow: 'hidden',
      }}
    >
      {/* The Glow */}
      <div
        style={{
          position: 'absolute',
          left: position.x,
          top: position.y,
          width: 400,
          height: 400,
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(255, 255, 255, 0.04) 0%, transparent 60%)',
          borderRadius: '50%',
          mixBlendMode: 'screen',
          willChange: 'left, top',
        }}
      />
      {/* The Pixelation Mask Overlay */}
      <div
        style={{
          position: 'absolute',
          left: position.x,
          top: position.y,
          width: 250,
          height: 250,
          transform: 'translate(-50%, -50%)',
          background: 'radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 50%)',
          borderRadius: '50%',
          mixBlendMode: 'overlay',
          willChange: 'left, top',
          /* Creating a subtle pixel grid pattern using background-image */
          maskImage: 'url("data:image/svg+xml,%3Csvg width=\'4\' height=\'4\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Crect width=\'2\' height=\'2\' fill=\'black\'/%3E%3C/svg%3E")',
          WebkitMaskImage: 'url("data:image/svg+xml,%3Csvg width=\'4\' height=\'4\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Crect width=\'2\' height=\'2\' fill=\'black\'/%3E%3C/svg%3E")',
          maskSize: '4px 4px',
          WebkitMaskSize: '4px 4px',
          maskRepeat: 'repeat',
          WebkitMaskRepeat: 'repeat',
        }}
      />
    </div>
  )
}
