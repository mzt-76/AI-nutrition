/** Session storage keys for conversation persistence across tab navigation. */
export const SESSION_KEY = 'active_conversation_id';
export const SESSION_CONV_KEY = 'active_conversation';
export const SESSION_MESSAGES_KEY = 'active_messages';

/** Polling delays (ms) for tracking input — exponential backoff. */
export const TRACKING_POLL_DELAYS = [1000, 2000, 3000, 4000, 5000];
