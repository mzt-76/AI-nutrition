import { useState, useMemo, useCallback, memo } from 'react';
import remarkGfm from 'remark-gfm';
import breaks from 'remark-breaks';
import { Message, FileAttachment } from '@/types/database.types';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Check, Copy, User, FileText, Download } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import ReactMarkdown from 'react-markdown';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { cn } from '@/lib/utils';
import { safeWriteClipboard } from '@/lib/clipboard';
import { ComponentRenderer } from '@/components/generative-ui/ComponentRenderer';
import type { MealDataFromPlan } from '@/components/recipes/RecipeDetailDrawer';
import { UIComponentBlock } from '@/types/generative-ui.types';
import { logger } from '@/lib/logger';

export type { MealDataFromPlan };

interface MessageItemProps {
  message: Message;
  isLastMessage?: boolean;
  onAction?: (value: string) => void;
  onMealClick?: (data: MealDataFromPlan) => void;
}

interface CodeProps {
  inline?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const MessageItem = memo(({ message, isLastMessage = false, onAction, onMealClick }: MessageItemProps) => {
  const [copied, setCopied] = useState(false);

  const handleMealClick = useCallback((comp: UIComponentBlock) => {
    if (!onMealClick) return;
    const p = comp.props;
    const macros = (p.macros ?? {}) as { protein_g?: number; carbs_g?: number; fat_g?: number };
    onMealClick({
      name: (p.recipe_name as string) ?? '',
      meal_type: (p.meal_type as string) ?? '',
      ingredients: ((p.ingredients as string[]) ?? []),
      instructions: (p.instructions as string) ?? undefined,
      prep_time_minutes: (p.prep_time as number) ?? undefined,
      nutrition: {
        calories: (p.calories as number) ?? 0,
        protein_g: macros.protein_g ?? 0,
        carbs_g: macros.carbs_g ?? 0,
        fat_g: macros.fat_g ?? 0,
      },
    });
  }, [onMealClick]);

  const handleCopy = async () => {
    await safeWriteClipboard(message.message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Properly check if the message is from AI (lowercase 'ai') or user
  const isAI = message.message.type.toLowerCase() === 'ai';
  const isUser = !isAI;

  const hasFiles = (message.message.files?.length ?? 0) > 0;
  
  // Function to download a file
  const downloadFile = (file: FileAttachment) => {
    try {
      // Convert base64 to blob
      let byteCharacters: string;
      try {
        byteCharacters = atob(file.content);
      } catch {
        logger.error('Invalid base64 in file attachment:', file.fileName);
        return;
      }
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: file.mimeType });

      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      logger.error('Failed to download file attachment:', e);
    }
  };
  
  // Memoize the markdown content to prevent unnecessary re-renders
  // This is especially important for the first AI response
  const memoizedMarkdown = useMemo(() => {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm, breaks]} // Add GFM support and preserve line breaks
        components={{
          // Add proper paragraph handling with increased spacing
          p: ({children}) => <p className="mb-6 last:mb-0">{children}</p>,
          // Ensure proper link styling with a distinct color
          a: ({href, children}) => {
            let isSafe = false;
            if (href) {
              try {
                const url = new URL(href);
                isSafe = url.protocol === 'http:' || url.protocol === 'https:';
              } catch {
                isSafe = false;
              }
            }
            return isSafe
              ? <a href={href} className="text-blue-400 hover:text-blue-500 hover:underline" target="_blank" rel="noopener noreferrer">{children}</a>
              : <span className="text-blue-400">{children}</span>;
          },
          // Ensure proper line break handling
          br: () => <br className="mb-2" />,
          // Handle code blocks with syntax highlighting
          code({node: _node, inline, className, children, ...props}: CodeProps) {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <SyntaxHighlighter
                style={atomDark}
                language={match[1]}
                PreTag="div"
                className="rounded-md !bg-gray-900 !p-4 !my-2"
                {...props}
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code className={cn("bg-gray-800 px-1 py-0.5 rounded text-gray-200", className)} {...props}>
                {children}
              </code>
            );
          }
        }}
      >
        {message.message.content ?? ''}
      </ReactMarkdown>
    );
  }, [message.message.content]);

  return (
    <div 
      className={cn(
        "flex w-full",
        isLastMessage && isAI && "animate-fade-in"
      )}
    >
      <div className={cn(
        "flex items-start gap-3 w-full max-w-4xl mx-auto px-4",
        isUser ? "justify-end" : "justify-start",
        "group"
      )}>
        {!isUser && (
          <div className="h-8 w-8 rounded-full gradient-green flex items-center justify-center text-white shrink-0 mt-1 text-xs font-bold">
            NIA
          </div>
        )}
        
        <div className={cn(
          "flex flex-col space-y-1",
          "max-w-[calc(100%-64px)]",
        )}>
          <div className="text-xs font-medium text-muted-foreground">
            {isUser ? 'Vous' : 'Assistant Nutrition IA'}
          </div>
          
          <div className={cn(
            "rounded-lg px-4 py-3 break-words",
            "overflow-x-auto", // Add horizontal scrolling for code blocks if needed
            isUser ? "bg-chat-user text-white" : "glass-effect text-foreground"
          )}>
            {/* File attachments */}
            {hasFiles && (
              <div className="mb-3 flex flex-wrap gap-2">
                {message.message.files?.map((file, index) => (
                  <Badge
                    key={`${file.fileName}-${index}`}
                    variant="outline" 
                    className="flex items-center gap-1 py-1 cursor-pointer hover:bg-secondary"
                    role="button"
                    aria-label={`Télécharger ${file.fileName}`}
                    onClick={() => downloadFile(file)}
                  >
                    <FileText className="h-3 w-3" />
                    <span className="max-w-[150px] truncate">{file.fileName}</span>
                    <Download className="h-3 w-3 ml-1" />
                  </Badge>
                ))}
              </div>
            )}
            <div className="prose prose-sm dark:prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&>p]:mb-4">
              {memoizedMarkdown}
            </div>
            {isAI && message.message.ui_components && message.message.ui_components.length > 0 && (
              <ComponentRenderer
                components={message.message.ui_components as UIComponentBlock[]}
                onAction={onAction}
                onMealClick={handleMealClick}
              />
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <div className="text-xs text-muted-foreground">
              {message.created_at ? new Date(message.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : ''}
            </div>
            
            {!isUser && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                onClick={handleCopy}
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                <span className="sr-only">Copier le message</span>
              </Button>
            )}
          </div>
        </div>
        
        {isUser && (
          <Avatar className="h-8 w-8 bg-secondary text-secondary-foreground shrink-0 mt-1">
            <AvatarFallback>
              <User className="h-5 w-5" />
            </AvatarFallback>
          </Avatar>
        )}
      </div>
    </div>
  );
});

MessageItem.displayName = 'MessageItem';
