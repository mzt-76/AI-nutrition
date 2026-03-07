import { toast } from "@/hooks/use-toast";

/**
 * Safely write text to the clipboard with a toast fallback
 * when the Clipboard API is unavailable (e.g. non-HTTPS contexts).
 */
export async function safeWriteClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    toast({
      title: "Copie impossible",
      description:
        "Le presse-papiers n'est pas disponible dans ce contexte (HTTP).",
      variant: "destructive",
    });
  }
}
