
import { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface TruncatedTextProps extends HTMLAttributes<HTMLSpanElement> {
  text: string;
  maxLength?: number;
}

export const TruncatedText = ({ 
  text, 
  maxLength = 25,
  className,
  ...props 
}: TruncatedTextProps) => {
  const truncatedText = text.length > maxLength 
    ? `${text.substring(0, maxLength)}...` 
    : text;

  return (
    <span 
      className={cn("whitespace-nowrap overflow-hidden text-ellipsis", className)}
      title={text} // Show full text on hover
      {...props}
    >
      {truncatedText}
    </span>
  );
};
