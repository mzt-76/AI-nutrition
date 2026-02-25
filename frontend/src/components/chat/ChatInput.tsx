
import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Send, Paperclip, X, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { FileAttachment } from '@/types/database.types';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';

interface ChatInputProps {
  onSendMessage: (message: string, files?: FileAttachment[]) => void;
  isLoading: boolean;
}

export const ChatInput = ({ onSendMessage, isLoading }: ChatInputProps) => {
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<FileAttachment[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((message.trim() || files.length > 0) && !isLoading) {
      // Enforce the 4,000 character limit before sending
      const truncatedMessage = message.slice(0, 4000);
      onSendMessage(truncatedMessage, files.length > 0 ? files : undefined);
      setMessage('');
      setFiles([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 200); // Cap height at 200px
      textarea.style.height = `${newHeight}px`;
    }
  }, [message]);

  // Reset textarea height on mobile when component mounts
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }, []);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles) return;

    // Check if adding these files would exceed the limit
    if (files.length + selectedFiles.length > 5) {
      toast({
        title: "Limite de fichiers atteinte",
        description: "Vous pouvez télécharger jusqu'à 5 fichiers",
        variant: "destructive"
      });
      return;
    }

    // Process each file
    Array.from(selectedFiles).forEach(file => {
      // Check file size (1MB = 1048576 bytes)
      if (file.size > 1048576) {
        toast({
          title: "Fichier trop volumineux",
          description: `${file.name} dépasse la limite de 1 Mo`,
          variant: "destructive"
        });
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          // Extract the base64 data (remove the prefix like "data:image/png;base64,")
          const base64Content = event.target.result.toString();
          const base64Data = base64Content.split(',')[1] || base64Content;
          
          setFiles(prevFiles => [
            ...prevFiles,
            {
              fileName: file.name,
              content: base64Data,
              mimeType: file.type || 'application/octet-stream'
            }
          ]);
        }
      };
      reader.readAsDataURL(file);
    });

    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number) => {
    setFiles(prevFiles => prevFiles.filter((_, i) => i !== index));
  };

  return (
    <div className="w-full">
      {/* File attachments container - separate from the main input */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 p-2 mb-2 border rounded-lg bg-background">
          {files.map((file, index) => (
            <Badge key={index} variant="secondary" className="flex items-center gap-1 py-1">
              <FileText className="h-3 w-3" />
              <span className="max-w-[150px] truncate">{file.fileName}</span>
              <Button 
                type="button" 
                variant="ghost" 
                size="sm" 
                className="h-4 w-4 p-0 ml-1"
                onClick={() => removeFile(index)}
              >
                <X className="h-3 w-3" />
                <span className="sr-only">Remove file</span>
              </Button>
            </Badge>
          ))}
        </div>
      )}
      
      {/* Main input form - always centered */}
      <form 
        onSubmit={handleSubmit}
        className="relative flex w-full flex-col rounded-lg border bg-background shadow-sm overflow-hidden"
      >
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value.slice(0, 4000))} // Limit to 4000 chars
          onKeyDown={handleKeyDown}
          placeholder={files.length > 0 ? "Ajoutez un message ou envoyez les fichiers..." : "Posez votre question..."}
          className="min-h-[56px] max-h-[200px] resize-none border-0 py-3 px-3 pr-36 focus-visible:ring-0 focus-visible:ring-offset-0"
          style={{ 
            height: 'auto',
            wordBreak: 'break-word',
            overflowWrap: 'break-word',
            whiteSpace: 'pre-wrap',
            width: 'calc(100% - 30px)'
          }}
          disabled={isLoading}
          maxLength={4000}
        />
        <input 
          type="file" 
          ref={fileInputRef}
          className="hidden" 
          onChange={handleFileUpload}
          multiple
          accept="*/*"
        />
        <div className="absolute right-2 top-0 bottom-0 flex items-center justify-center h-full">
          <div className={`text-xs mr-2 ${message.length >= 4000 ? 'text-red-500 font-semibold' : 'text-muted-foreground'}`}>
            {message.length} / 4000
          </div>
          
          {/* File upload button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className={cn("mr-1", files.length >= 5 && "opacity-50 cursor-not-allowed")}
                disabled={isLoading || files.length >= 5}
                onClick={() => {
                  fileInputRef.current?.click();
                }}
              >
                <Paperclip className="h-4 w-4" />
                <span className="sr-only">Upload file</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              {files.length >= 5 ? "Limite atteinte (5 max)" : "Télécharger des fichiers (1 Mo max)"}
            </TooltipContent>
          </Tooltip>
          
          <Button
            type="submit"
            size="sm"
            variant="default"
            disabled={(message.trim() === '' && files.length === 0) || isLoading}
            className={cn(
              "transition-all gradient-green text-white",
              (message.trim() === '' && files.length === 0) ? "opacity-60" : "opacity-100",
              isLoading ? "opacity-50 cursor-not-allowed" : ""
            )}
          >
            <Send className="h-4 w-4" />
            <span className="sr-only">Envoyer</span>
          </Button>
        </div>
      </form>
    </div>
  );
};
