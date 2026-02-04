type MessageHandler = (data: any) => void;

export class PersonaWebSocket {
    private ws: WebSocket | null = null;
    private handlers: MessageHandler[] = [];
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;

    connect(personaId: string) {
        const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8001';
        this.ws = new WebSocket(`${wsUrl}/ws/chat/${personaId}`);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handlers.forEach((handler) => handler(data));
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket closed');
            this.attemptReconnect(personaId);
        };
    }

    private attemptReconnect(personaId: string) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                console.log(`Reconnecting... (${this.reconnectAttempts})`);
                this.connect(personaId);
            }, this.reconnectDelay * this.reconnectAttempts);
        }
    }

    send(message: string) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ message }));
        }
    }

    onMessage(handler: MessageHandler) {
        this.handlers.push(handler);
    }

    disconnect() {
        this.ws?.close();
        this.handlers = [];
    }
}