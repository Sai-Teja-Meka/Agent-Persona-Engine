export interface PersonaInfo {
    persona_id: string;
    name: string;
    domain: string;
    expertise_areas: string[];
    credibility_score: number;
    description: string;
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    context?: {
        memories_count?: number;
        facts_count?: number;
        summaries_count?: number;
    };
}

export interface ChatResponse {
    response: string;
    context_used: {
        memories?: string[];
        facts?: string[];
        summaries?: string[];
    };
    latency_ms: number;
}

export interface GraphNode {
    id: string;
    label: string;
    type: 'expert' | 'domain' | 'problem';
    properties: Record<string, any>;
}

export interface GraphEdge {
    id: string;
    source: string;
    target: string;
    label: string;
}

export interface SystemAnalytics {
    expert_count: number;
    domain_count: number;
    problem_count: number;
    memory_raw: number;
    memory_summary: number;
}