
import { Conversation, Message } from '@/types/database.types';

export interface ConversationDetails extends Conversation {
  messages?: Message[];
}
