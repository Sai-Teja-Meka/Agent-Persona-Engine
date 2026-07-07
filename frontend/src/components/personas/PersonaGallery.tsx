import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Brain, TrendingUp, Sparkles } from 'lucide-react';
import { api } from '../../services/api';
import { usePersonaStore } from '../../stores/usePersonaStore';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';

export function PersonaGallery() {
    const { selectPersona } = usePersonaStore();

    const { data: personas, isLoading } = useQuery({
        queryKey: ['personas'],
        queryFn: api.getPersonas,
    });

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-16 h-16 border-4 border-primary-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-dark-400">Loading personas...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8">
            {/* Header */}
            <div className="mb-8">
                <h2 className="text-3xl font-bold gradient-text mb-2">
                    Expert Personas
                </h2>
                <p className="text-dark-400">
                    Select an expert to consult with based on their domain expertise
                </p>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                <Card glass>
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-lg bg-primary-500/10 flex items-center justify-center">
                            <Brain className="w-6 h-6 text-primary-400" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-white">{personas?.length || 0}</p>
                            <p className="text-sm text-dark-400">Active Experts</p>
                        </div>
                    </div>
                </Card>

                <Card glass>
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-lg bg-green-500/10 flex items-center justify-center">
                            <Sparkles className="w-6 h-6 text-green-400" />
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-white">
                                {new Set(personas?.flatMap(p => p.expertise_areas)).size || 0}
                            </p>
                            <p className="text-sm text-dark-400">Domains Covered</p>
                        </div>
                    </div>
                </Card>

            </div>

            {/* Persona Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {personas?.map((persona, index) => (
                    <motion.div
                        key={persona.persona_id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                    >
                        <Card
                            hover
                            glass
                            onClick={() => selectPersona(persona)}
                        >
                            {/* Header */}
                            <div className="flex items-start gap-4 mb-4">
                                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center flex-shrink-0">
                                    <Brain className="w-7 h-7 text-white" />
                                </div>

                                <div className="flex-1 min-w-0">
                                    <h3 className="text-lg font-semibold text-white truncate">
                                        {persona.name}
                                    </h3>
                                    <p className="text-sm text-primary-400">{persona.domain}</p>
                                </div>
                            </div>

                            {/* Description */}
                            <p className="text-sm text-dark-300 mb-4 line-clamp-3">
                                {persona.description}
                            </p>

                            {/* Metrics */}
                            <div className="flex items-center gap-4 mb-4 pb-4 border-b border-dark-800">
                                <div className="flex items-center gap-1.5">
                                    <TrendingUp className="w-4 h-4 text-green-500" />
                                    <span className="text-sm font-medium text-white">
                                        {persona.expertise_areas.length} domains
                                    </span>
                                </div>
                            </div>

                            {/* Expertise Tags */}
                            <div className="flex flex-wrap gap-2">
                                {persona.expertise_areas.slice(0, 3).map((area) => (
                                    <Badge key={area} variant="primary" size="sm">
                                        {area}
                                    </Badge>
                                ))}
                                {persona.expertise_areas.length > 3 && (
                                    <Badge variant="default" size="sm">
                                        +{persona.expertise_areas.length - 3}
                                    </Badge>
                                )}
                            </div>
                        </Card>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}