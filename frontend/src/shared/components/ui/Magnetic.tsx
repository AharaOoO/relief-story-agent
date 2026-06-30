import React, { useRef, useState } from 'react';
import { useMotionValue, useSpring } from 'framer-motion';

interface MagneticProps {
  children: React.ReactElement<any>;
  springOptions?: { stiffness: number; damping: number; mass: number };
  actionArea?: 'parent' | 'global';
  intensity?: number;
}

export function Magnetic({
  children,
  springOptions = { stiffness: 150, damping: 15, mass: 0.1 },
  intensity = 0.5,
}: MagneticProps) {
  const ref = useRef<HTMLElement>(null);
  const [isHovered, setIsHovered] = useState(false);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const springX = useSpring(x, springOptions);
  const springY = useSpring(y, springOptions);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!ref.current) return;
    const { clientX, clientY } = e;
    const { height, width, left, top } = ref.current.getBoundingClientRect();
    const middleX = clientX - (left + width / 2);
    const middleY = clientY - (top + height / 2);
    
    x.set(middleX * intensity);
    y.set(middleY * intensity);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
    x.set(0);
    y.set(0);
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  return React.cloneElement(children, {
    ref,
    onMouseMove: handleMouseMove,
    onMouseLeave: handleMouseLeave,
    onMouseEnter: handleMouseEnter,
    style: {
      ...children.props.style,
      x: springX,
      y: springY,
      transition: isHovered ? 'none' : 'transform 0.3s ease-out',
    },
  });
}
