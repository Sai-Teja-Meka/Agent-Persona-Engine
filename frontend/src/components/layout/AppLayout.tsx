import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, MessageSquare, Network, BarChart3, Menu, X } from 'lucide-react';

type View = 'personas' | 'chat' | 'graph' | 'analytics';

interface AppLayoutProps {
    children: React.ReactNode;
    currentView: View;
    onViewChange: (view: View) => void;
}

export function AppLayout({ children, currentView, onViewChange }: AppLayoutProps) {
    const [sidebarOpen, setSidebarOpen] = useState(true);

    const navItems: Array<{ id: View; icon: React.ElementType; label: string }> = [
        { id: 'personas', icon: Brain, label: 'Personas' },
        { id: 'chat', icon: MessageSquare, label: 'Chat' },
        { id: 'graph', icon: Network, label: 'Knowledge Graph' },
        { id: 'analytics', icon: BarChart3, label: 'Analytics' },
    ];

    return (
        <div className="flex h-screen bg-dark-950 overflow-hidden">
            {/* Sidebar */}
            <AnimatePresence>
                {sidebarOpen && (
                    <motion.aside
                        initial={{ x: -280 }}
                        animate={{ x: 0 }}
                        exit={{ x: -280 }}
                        transition={{ type: 'spring', damping: 25 }}
                        className="w-70 glass-effect border-r border-dark-800 flex flex-col"
                    >
                        {/* Logo */}
                        <div className="p-6 border-b border-dark-800">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                                    <Brain className="w-6 h-6 text-white" />
                                </div>
                                <div>
                                    <h1 className="text-lg font-bold gradient-text">Persona Engine</h1>
                                    <p className="text-xs text-dark-400">Expert AI System</p>
                                </div>
                            </div>
                        </div>

                        {/* Navigation */}
                        <nav className="flex-1 p-4 space-y-2">
                            {navItems.map((item) => {
                                const Icon = item.icon;
                                const isActive = currentView === item.id;

                                return (
                                    <button
                                        key={item.id}
                                        onClick={() => onViewChange(item.id)}
                                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${isActive
                                                ? 'bg-primary-600 text-white'
                                                : 'text-dark-400 hover:bg-dark-800 hover:text-dark-100'
                                            }`}
                                    >
                                        <Icon className="w-5 h-5" />
                                        <span className="font-medium">{item.label}</span>
                                    </button>
                                );
                            })}
                        </nav>

                        {/* Footer */}
                        <div className="p-4 border-t border-dark-800">
                            <div className="text-xs text-dark-500">
                                <div className="flex items-center gap-2 mb-2">
                                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                                    <span>System Online</span>
                                </div>
                                <p>v2.0.0 • Built with ∞</p>
                            </div>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* Main Content */}
            <div className="flex-1 flex flex-col">
                {/* Header */}
                <header className="glass-effect border-b border-dark-800 px-6 py-4">
                    <div className="flex items-center justify-between">
                        <button
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            className="p-2 hover:bg-dark-800 rounded-lg transition-colors"
                            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
                        >
                            {sidebarOpen ? (
                                <X className="w-5 h-5 text-dark-400" />
                            ) : (
                                <Menu className="w-5 h-5 text-dark-400" />
                            )}
                        </button>

                        <div className="flex items-center gap-4">
                            <div className="text-right">
                                <p className="text-sm text-dark-400">Current View</p>
                                <p className="font-medium text-dark-100">
                                    {navItems.find((i) => i.id === currentView)?.label}
                                </p>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Content Area */}
                <main className="flex-1 overflow-auto">
                    <motion.div
                        key={currentView}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        className="h-full"
                    >
                        {children}
                    </motion.div>
                </main>
            </div>
        </div>
    );
}
