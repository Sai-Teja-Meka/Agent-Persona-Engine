import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader2, Brain, ChevronDown, Info } from 'lucide-react';
import { usePersonaStore } from '../../stores/usePersonaStore';
import { useChatStore } from '../../stores/useChatStore';
import { PersonaWebSocket } from '../../services/websocket';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

export function ChatInterface() {
    const { selectedPersona } = usePersonaStore();
    const { messages, isTyping, contextInfo, addMessage, setTyping, setContextInfo, clearMessages } = useChatStore();

    const [input, setInput] = useState('');
    const [showContext, setShowContext] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const wsRef = useRef<PersonaWebSocket | null>(null);

    useEffect(() => {
        if (!selectedPersona) return;

        // Initialize WebSocket
        wsRef.current = new PersonaWebSocket();
        wsRef.current.connect(selectedPersona.persona_id);

        wsRef.current.onMessage((data) => {
            if (data.type === 'typing') {
                setTyping(data.status === 'started');
            } else if (data.type === 'message') {
                addMessage({
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: data.content,
                    timestamp: new Date(),
                    context: data.context,
                });
                setContextInfo(data.context);
                setTyping(false);
            }
        });

        return () => {
            wsRef.current?.disconnect();
        };
    }, [selectedPersona]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || !selectedPersona) return;

        const userMessage = {
            id: Date.now().toString(),
            role: 'user' as const,
            content: input,
            timestamp: new Date(),
        };

        addMessage(userMessage);
        setInput('');

        // Send via WebSocket
        wsRef.current?.send(input);
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    if (!selectedPersona) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <Brain className="w-16 h-16 text-dark-700 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-dark-300 mb-2">
                        No Persona Selected
                    </h3>
                    <p className="text-dark-500">
                        Select an expert persona to start consulting
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full bg-dark-950">
            {/* Chat Header */}
            <div className="glass-effect border-b border-dark-800 p-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                            <Brain className="w-6 h-6 text-white" />
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-white">
                                {selectedPersona.name}
                            </h2>
                            <p className="text-sm text-dark-400">{selectedPersona.domain}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowContext(!showContext)}
                            leftIcon={<Info className="w-4 h-4" />}
                        >
                            Context
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearMessages}
                        >
                            Clear Chat
                        </Button>
                    </div>
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.length === 0 && (
                    <div className="text-center py-12">
                        <Brain className="w-16 h-16 text-dark-700 mx-auto mb-4" />
                        <h3 className="text-lg font-semibold text-dark-300 mb-2">
                            Start a Conversation
                        </h3>
                        <p className="text-dark-500 mb-6">
                            Ask {selectedPersona.name} anything about {selectedPersona.domain}
                        </p>

                        <div className="max-w-2xl mx-auto">
                            <p className="text-sm text-dark-600 mb-3">Suggested questions:</p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {[
                                    'What are your areas of expertise?',
                                    'Can you help me solve a problem?',
                                    'What is your approach to problem-solving?',
                                    'Tell me about your experience',
                                ].map((suggestion) => (
                                    <button
                                        key={suggestion}
                                        onClick={() => setInput(suggestion)}
                                        className="text-left p-3 rounded-lg bg-dark-900 border border-dark-800 hover:border-primary-600 transition-colors text-sm text-dark-300"
                                    >
                                        {suggestion}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {messages.map((message, index) => (
                    <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[75%] ${message.role === 'user'
                                    ? 'bg-primary-600 text-white'
                                    : 'glass-effect text-dark-100'
                                } rounded-2xl p-4`}
                        >
                            <p className="whitespace-pre-wrap leading-relaxed">
                                {message.content}
                            </p>

                            {message.context && (
                                <div className="mt-3 pt-3 border-t border-dark-700/50 flex gap-2 text-xs">
                                    <Badge variant="default" size="sm">
                                        {message.context.memories_count} memories
                                    </Badge>
                                    <Badge variant="default" size="sm">
                                        {message.context.facts_count} facts
                                    </Badge>
                                    <Badge variant="default" size="sm">
                                        {message.context.summaries_count} summaries
                                    </Badge>
                                </div>
                            )}

                            <span className="text-xs opacity-60 mt-2 block">
                                {message.timestamp.toLocaleTimeString()}
                            </span>
                        </div>
                    </motion.div>
                ))}

                {isTyping && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex justify-start"
                    >
                        <div className="glass-effect rounded-2xl p-4 flex items-center gap-2">
                            <Loader2 className="w-4 h-4 animate-spin text-primary-500" />
                            <span className="text-dark-400 text-sm">
                                {selectedPersona.name} is thinking...
                            </span>
                        </div>
                    </motion.div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Context Panel */}
            <AnimatePresence>
                {showContext && contextInfo && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="border-t border-dark-800 overflow-hidden"
                    >
                        <div className="p-4 bg-dark-900/50">
                            <div className="flex items-center gap-2 mb-3">
                                <Info className="w-4 h-4 text-primary-500" />
                                <h3 className="text-sm font-semibold text-white">
                                    Retrieval Context
                                </h3>
                                <button
                                    onClick={() => setShowContext(false)}
                                    className="ml-auto text-dark-500 hover:text-dark-300"
                                >
                                    <ChevronDown className="w-4 h-4" />
                                </button>
                            </div>

                            <div className="grid grid-cols-3 gap-4 text-xs">
                                <div>
                                    <p className="text-dark-500 mb-1">Memories</p>
                                    <p className="text-primary-400 font-semibold">
                                        {contextInfo.memories_count || 0} retrieved
                                    </p>
                                </div>
                                <div>
                                    <p className="text-dark-500 mb-1">Facts</p>
                                    <p className="text-primary-400 font-semibold">
                                        {contextInfo.facts_count || 0} retrieved
                                    </p>
                                </div>
                                <div>
                                    <p className="text-dark-500 mb-1">Summaries</p>
                                    <p className="text-primary-400 font-semibold">
                                        {contextInfo.summaries_count || 0} retrieved
                                    </p>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Input Area */}
            <div className="glass-effect border-t border-dark-800 p-4">
                <div className="flex gap-3">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyPress}
                        placeholder={`Ask ${selectedPersona.name} anything...`}
                        className="flex-1 bg-dark-900 text-white rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-600 resize-none"
                        rows={2}
                        disabled={isTyping}
                    />
                    <Button
                        onClick={handleSend}
                        disabled={isTyping || !input.trim()}
                        size="lg"
                        leftIcon={<Send className="w-5 h-5" />}
                    >
                        Send
                    </Button>
                </div>

                <div className="flex items-center gap-2 mt-2 text-xs text-dark-500">
                    <span>Press Enter to send, Shift+Enter for new line</span>
                </div>
            </div>
        </div>
    );
}