import { create } from 'zustand';
import type { PersonaInfo } from '../services/types';

interface PersonaStore {
    personas: PersonaInfo[];
    selectedPersona: PersonaInfo | null;
    isLoading: boolean;
    error: string | null;
    setPersonas: (personas: PersonaInfo[]) => void;
    selectPersona: (persona: PersonaInfo | null) => void;
    setLoading: (loading: boolean) => void;
    setError: (error: string | null) => void;
}

export const usePersonaStore = create<PersonaStore>((set) => ({
    personas: [],
    selectedPersona: null,
    isLoading: false,
    error: null,
    setPersonas: (personas) => set({ personas }),
    selectPersona: (persona) => set({ selectedPersona: persona }),
    setLoading: (loading) => set({ isLoading: loading }),
    setError: (error) => set({ error }),
}));