import axios from 'axios';
import type {
    PersonaInfo,
    ChatResponse,
    GraphNode,
    GraphEdge,
    SystemAnalytics,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api';

const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const api = {
    // Personas
    async getPersonas(): Promise<PersonaInfo[]> {
        const { data } = await client.get('/personas');
        return data;
    },

    async getPersona(personaId: string): Promise<PersonaInfo> {
        const { data } = await client.get(`/personas/${personaId}`);
        return data;
    },

    // Chat
    async sendMessage(
        personaId: string,
        message: string
    ): Promise<ChatResponse> {
        const { data } = await client.post('/chat', {
            persona_id: personaId,
            message,
            include_context: true,
        });
        return data;
    },

    // Graph
    async getExpertGraph(
        personaId: string,
        depth: number = 2
    ): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
        const { data } = await client.get(`/graph/expert/${personaId}`, {
            params: { depth },
        });
        return data;
    },

    async getDomains(): Promise<any[]> {
        const { data } = await client.get('/graph/domains');
        return data;
    },

    // Analytics
    async getSystemAnalytics(): Promise<SystemAnalytics> {
        const { data } = await client.get('/analytics/system');
        return data;
    },

    async getPersonaAnalytics(personaId: string): Promise<any> {
        const { data } = await client.get(`/analytics/persona/${personaId}`);
        return data;
    },
};