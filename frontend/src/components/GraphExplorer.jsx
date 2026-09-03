import React, { useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Network, ZoomIn } from 'lucide-react';

export default function GraphExplorer({ graphData, selectedNode, onSelectNode }) {
  const fgRef = useRef();

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge').strength(-180);
    }
  }, [graphData]);

  const getNodeColor = (node) => {
    if (node.risk_tier === 'CRITICAL') return '#EF4444';
    if (node.risk_tier === 'HIGH') return '#F97316';
    if (node.risk_tier === 'MEDIUM') return '#F59E0B';
    return '#10B981';
  };

  return (
    <div className="bg-surface border border-border rounded-xl flex flex-col h-[580px] overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between bg-card/50">
        <div className="flex items-center space-x-2">
          <Network className="w-4 h-4 text-purple-400" />
          <h2 className="text-sm font-semibold text-white">Interactive Graph & Ring Forensics</h2>
        </div>
        <div className="flex items-center space-x-3 text-xs text-gray-400">
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            <span>Mule / Risky</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span>Normal</span>
          </span>
        </div>
      </div>

      <div className="flex-1 bg-black/40 relative">
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeLabel={(node) => `${node.id} (${node.label || 'Account'}) - Tier: ${node.risk_tier}`}
          nodeColor={getNodeColor}
          nodeVal={(node) => (node.is_focus ? 10 : 6)}
          linkColor={(link) => (link.is_risky || link.gat_attention > 0.7 ? '#EF4444' : '#374151')}
          linkWidth={(link) => (link.gat_attention ? link.gat_attention * 3.5 : 1.5)}
          linkDirectionalParticles={2}
          linkDirectionalParticleSpeed={(link) => (link.is_risky ? 0.008 : 0.003)}
          linkDirectionalParticleWidth={2.5}
          linkDirectionalParticleColor={(link) => (link.is_risky ? '#F87171' : '#60A5FA')}
          onNodeClick={(node) => onSelectNode && onSelectNode(node)}
          width={650}
          height={520}
        />
      </div>
    </div>
  );
}
