import { create } from 'zustand';
import type { ChatMessage } from '../services/types';

interface ChatStore {
    messages: ChatMessage[];
    isTyping: boolean;
    contextInfo: any | null;
    addMessage: (message: ChatMessage) => void;
    setTyping: (typing: boolean) => void;
    setContextInfo: (info: any) => void;
    clearMessages: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
    messages: [],
    isTyping: false,
    contextInfo: null,
    addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),
    setTyping: (typing) => set({ isTyping: typing }),
    setContextInfo: (info) => set({ contextInfo: info }),
    clearMessages: () => set({ messages: [] }),
}));