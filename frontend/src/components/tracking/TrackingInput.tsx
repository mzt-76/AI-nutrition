import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, Mic, Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { sendMessage } from '@/lib/api';

interface TrackingInputProps {
  dateStr: string;
  onEntryCreated: () => void;
}

export function TrackingInput({ dateStr, onEntryCreated }: TrackingInputProps) {
  const { user, session } = useAuth();
  const { toast } = useToast();
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  const handleSpeechResult = useCallback((transcript: string) => {
    setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
    inputRef.current?.focus();
  }, []);

  const handleSpeechError = useCallback(
    (error: string) => {
      toast({ variant: 'destructive', title: 'Micro', description: error });
    },
    [toast],
  );

  const { isListening, startListening, stopListening, isSupported } = useSpeechRecognition({
    onResult: handleSpeechResult,
    onError: handleSpeechError,
  });

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || !user || sending) return;

    // Cancel any in-flight poll from a previous submit
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);

    setSending(true);
    try {
      const prompt = `[SUIVI RAPIDE - date: ${dateStr}] L'utilisateur déclare avoir mangé : "${trimmed}". Enregistre ces aliments dans le journal du ${dateStr}. Réponds uniquement par une confirmation courte.`;

      // Pass a no-op streaming callback so sendMessage uses the NDJSON
      // streaming path instead of trying to JSON.parse the full response.
      await sendMessage(prompt, user.id, '', session?.access_token, undefined, () => {});

      setText('');
      toast({ title: 'Envoyé', description: "L'agent analyse vos aliments..." });
      // Poll with exponential backoff — agent may need 5-10s for OFF lookups.
      // Cancel previous poll chain on re-submit or unmount via pollTimerRef.
      const delays = [1000, 2000, 3000, 4000, 5000];
      let attempt = 0;
      const poll = () => {
        if (attempt >= delays.length) return;
        pollTimerRef.current = setTimeout(async () => {
          await onEntryCreated();
          attempt++;
          poll();
        }, delays[attempt]);
      };
      poll();
    } catch (err) {
      console.error('Tracking input error:', err);
      toast({ variant: 'destructive', title: 'Erreur', description: "Impossible d'enregistrer le repas." });
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="fixed bottom-14 left-0 right-0 z-40 px-4 pb-3 pt-6 bg-gradient-to-t from-[hsl(220,15%,5%)] via-[hsl(220,15%,5%)/0.95] to-transparent pointer-events-none">
      <div
        className={`pointer-events-auto rounded-2xl border flex items-center gap-1.5 px-1.5 py-1 max-w-lg mx-auto transition-all duration-300
          ${isListening
            ? 'border-red-500/30 bg-red-500/[0.06] shadow-[0_0_20px_hsl(0,84%,60%/0.15)]'
            : 'border-white/10 glass-effect shadow-[0_4px_24px_rgba(0,0,0,0.4)]'
          }
        `}
      >
        {/* Mic button */}
        {isSupported && (
          <button
            onClick={isListening ? stopListening : startListening}
            className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 transition-all
              ${isListening
                ? 'bg-red-500/20 text-red-400'
                : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
              }
            `}
            style={isListening ? { animation: 'recording-pulse 2s ease-in-out infinite' } : undefined}
          >
            <Mic className="h-4 w-4" />
            <span className="sr-only">{isListening ? 'Arrêter le micro' : 'Activer le micro'}</span>
          </button>
        )}

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isListening ? 'Écoute en cours...' : "J'ai mangé..."}
          disabled={sending}
          className="flex-1 bg-transparent text-sm text-gray-200 placeholder:text-gray-600 outline-none min-w-0 py-2 px-1"
        />

        {/* Send button */}
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || sending}
          className="h-9 w-9 rounded-xl flex items-center justify-center shrink-0 transition-all
            bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30
            disabled:opacity-20 disabled:cursor-default disabled:hover:bg-emerald-500/20"
        >
          {sending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          <span className="sr-only">Envoyer</span>
        </button>
      </div>
    </div>
  );
}
