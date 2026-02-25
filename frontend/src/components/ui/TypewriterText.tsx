import { useState, useEffect } from 'react';

interface TypewriterTextProps {
  text: string;
  duration?: number; // Duration in milliseconds
  className?: string;
}

/**
 * A component that animates text with a typewriter effect.
 * 
 * @param text - The text to be animated
 * @param duration - The total duration of the animation in milliseconds (default: 300ms)
 * @param className - Additional CSS classes to apply to the text
 * @returns A React component with typewriter animation
 */
export const TypewriterText = ({
  text,
  duration = 300,
  className = '',
}: TypewriterTextProps) => {
  const [displayText, setDisplayText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    if (!text) {
      setDisplayText('');
      setIsComplete(false);
      return;
    }

    // Reset when text changes
    setDisplayText('');
    setIsComplete(false);
    
    const charactersPerStep = text.length > 0 ? text.length / (duration / 16.67) : 0;
    let currentLength = 0;
    let animationFrameId: number;

    const animateText = () => {
      currentLength += charactersPerStep;
      
      if (currentLength >= text.length) {
        setDisplayText(text);
        setIsComplete(true);
        return;
      }
      
      setDisplayText(text.slice(0, Math.floor(currentLength)));
      animationFrameId = requestAnimationFrame(animateText);
    };

    animationFrameId = requestAnimationFrame(animateText);

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [text, duration]);

  return (
    <span className={className}>
      {displayText}
      {!isComplete && <span className="animate-pulse">|</span>}
    </span>
  );
};
