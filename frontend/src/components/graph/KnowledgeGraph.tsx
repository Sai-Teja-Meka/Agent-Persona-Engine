import React, { useEffect, useState, useCallback } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    MarkerType,
    ConnectionMode,
} from 'reactflow';
import type{
    Node,
    Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useQuery } from '@tanstack/react-query';
import { Network, Loader2,} from 'lucide-react';
import { api } from '../../services/api';
import { usePersonaStore } from '../../stores/usePersonaStore';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

const nodeColors = {
    expert: '#3b82f6',
    character: '#3b82f6',
    domain: '#10b981',
    problem: '#f59e0b',
    scene: '#8b5cf6',
    chapter: '#ec4899',
    memory: '#6366f1',
    default: '#64748b',
};

export function KnowledgeGraph() {
    const { selectedPersona } = usePersonaStore();
    const [depth, setDepth] = useState(2);
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<any>(null);

    const { data: graphData, isLoading, refetch } = useQuery({
        queryKey: ['graph', selectedPersona?.persona_id, depth],
        queryFn: () =>
            selectedPersona
                ? api.getExpertGraph(selectedPersona.persona_id, depth)
                : Promise.resolve({ nodes: [], edges: [] }),
        enabled: !!selectedPersona,
    });

    useEffect(() => {
        if (!graphData) return;

        // Convert backend nodes to ReactFlow nodes
        const flowNodes: Node[] = graphData.nodes.map((node) => {
            const nodeType = node.type.toLowerCase();
            const color = nodeColors[nodeType as keyof typeof nodeColors] || nodeColors.default;

            return {
                id: node.id,
                type: 'default',
                position: { x: 0, y: 0 }, // Will be auto-laid out
                data: {
                    label: node.label,
                    type: node.type,
                    properties: node.properties,
                },
                style: {
                    background: color,
                    color: 'white',
                    border: '2px solid rgba(255,255,255,0.2)',
                    borderRadius: '12px',
                    padding: '12px 20px',
                    fontSize: '14px',
                    fontWeight: '600',
                },
            };
        });

        // Convert backend edges to ReactFlow edges
        const flowEdges: Edge[] = graphData.edges.map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.label,
            type: 'smoothstep',
            animated: true,
            style: { stroke: '#475569', strokeWidth: 2 },
            labelStyle: { fill: '#94a3b8', fontSize: 11 },
            labelBgStyle: { fill: '#1e293b' },
            markerEnd: {
                type: MarkerType.ArrowClosed,
                color: '#475569',
            },
        }));

        // Simple force-directed layout
        const layoutNodes = autoLayout(flowNodes, flowEdges);
        setNodes(layoutNodes);
        setEdges(flowEdges);
    }, [graphData, setNodes, setEdges]);

    const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
        setSelectedNode(node.data);
    }, []);

    if (!selectedPersona) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <Network className="w-16 h-16 text-dark-700 mx-auto mb-4" />
                    <h3 className="text-xl font-semibold text-dark-300 mb-2">
                        No Persona Selected
                    </h3>
                    <p className="text-dark-500">
                        Select a persona to visualize their knowledge graph
                    </p>
                </div>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <Loader2 className="w-16 h-16 animate-spin text-primary-500 mx-auto mb-4" />
                    <p className="text-dark-400">Loading knowledge graph...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="relative h-full bg-dark-950">
            {/* Controls Panel */}
            <div className="absolute top-4 left-4 z-10 space-y-2">
                <Card glass className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Network className="w-5 h-5 text-primary-500" />
                        <h3 className="font-semibold text-white">
                            {selectedPersona.name}'s Network
                        </h3>
                    </div>

                    <div className="space-y-3">
                        <div>
                            <label className="text-xs text-dark-400 mb-1 block">
                                Graph Depth
                            </label>
                            <div className="flex gap-2">
                                {[1, 2, 3].map((d) => (
                                    <button
                                        key={d}
                                        onClick={() => setDepth(d)}
                                        className={`px-3 py-1 rounded-lg text-sm transition-colors ${depth === d
                                                ? 'bg-primary-600 text-white'
                                                : 'bg-dark-800 text-dark-300 hover:bg-dark-700'
                                            }`}
                                    >
                                        {d}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => refetch()}
                            className="w-full"
                        >
                            Refresh Graph
                        </Button>
                    </div>
                </Card>

                {/* Legend */}
                <Card glass className="p-4">
                    <h4 className="text-xs font-semibold text-dark-400 mb-2">
                        Node Types
                    </h4>
                    <div className="space-y-1.5">
                        {Object.entries(nodeColors)
                            .filter(([key]) => key !== 'default')
                            .map(([type, color]) => (
                                <div key={type} className="flex items-center gap-2">
                                    <div
                                        className="w-3 h-3 rounded"
                                        style={{ backgroundColor: color }}
                                    />
                                    <span className="text-xs text-dark-300 capitalize">
                                        {type}
                                    </span>
                                </div>
                            ))}
                    </div>
                </Card>
            </div>

            {/* Node Details */}
            {selectedNode && (
                <div className="absolute top-4 right-4 z-10 w-80">
                    <Card glass className="p-4">
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <Badge variant="primary" size="sm">
                                    {selectedNode.type}
                                </Badge>
                                <h3 className="font-semibold text-white mt-2">
                                    {selectedNode.label}
                                </h3>
                            </div>
                            <button
                                onClick={() => setSelectedNode(null)}
                                className="text-dark-500 hover:text-dark-300"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="space-y-2 text-sm">
                            {Object.entries(selectedNode.properties || {})
                                .filter(([key]) => !key.startsWith('_'))
                                .slice(0, 5)
                                .map(([key, value]) => (
                                    <div key={key}>
                                        <span className="text-dark-500 capitalize">
                                            {key.replace('_', ' ')}:
                                        </span>
                                        <span className="text-dark-200 ml-2">
                                            {String(value).slice(0, 100)}
                                        </span>
                                    </div>
                                ))}
                        </div>
                    </Card>
                </div>
            )}

            {/* ReactFlow Graph */}
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                connectionMode={ConnectionMode.Loose}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.1}
                maxZoom={2}
            >
                <Background color="#1e293b" gap={16} />
                <Controls
                    showInteractive={false}
                    style={{
                        background: 'rgba(15, 23, 42, 0.8)',
                        border: '1px solid rgba(71, 85, 105, 0.5)',
                        borderRadius: '12px',
                    }}
                />
            </ReactFlow>

            {/* Stats */}
            <div className="absolute bottom-4 left-4 z-10">
                <Card glass className="p-3">
                    <div className="flex items-center gap-4 text-xs">
                        <div>
                            <span className="text-dark-500">Nodes:</span>
                            <span className="text-white ml-1 font-semibold">
                                {nodes.length}
                            </span>
                        </div>
                        <div>
                            <span className="text-dark-500">Edges:</span>
                            <span className="text-white ml-1 font-semibold">
                                {edges.length}
                            </span>
                        </div>
                    </div>
                </Card>
            </div>
        </div>
    );
}

// Simple auto-layout algorithm
function autoLayout(nodes: Node[], edges: Edge[]): Node[] {
    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;
    const radius = 300;

    return nodes.map((node, index) => {
        const angle = (index / nodes.length) * 2 * Math.PI;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);

        return {
            ...node,
            position: { x, y },
        };
    });
}