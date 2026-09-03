import React from 'react';
import { Zap, AlertTriangle, ShieldCheck, Flame } from 'lucide-react';

export default function AttackSimulatorPanel({ onInject }) {
  const attacks = [
    {
      id: 'ATO',
      title: 'Simulate ATO Drain',
      desc: 'Credential update followed by immediate high-value transfer.',
      amount: 49500,
      color: 'hover:border-red-500/50 hover:bg-red-500/10 text-red-300',
    },
    {
      id: 'SMURFING',
      title: 'Simulate Smurfing',
      desc: 'Rapid succession of sub-threshold structured transfers.',
      amount: 9800,
      color: 'hover:border-yellow-500/50 hover:bg-yellow-500/10 text-yellow-300',
    },
    {
      id: 'RING_WASH',
      title: 'Simulate Mule Ring Cycle',
      desc: 'Multi-party circular pass-through across 3 banks.',
      amount: 45000,
      color: 'hover:border-purple-500/50 hover:bg-purple-500/10 text-purple-300',
    },
  ];

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Flame className="w-4 h-4 text-orange-400" />
        <h3 className="text-sm font-semibold text-white">Adversarial Attack Simulator</h3>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {attacks.map((a) => (
          <button
            key={a.id}
            onClick={() => onInject(a.id, 'BANK01_ACC1042', a.amount)}
            className={`p-3 rounded-lg border border-border bg-card/60 text-left transition flex flex-col justify-between ${a.color}`}
          >
            <div>
              <p className="text-xs font-bold">{a.title}</p>
              <p className="text-[11px] text-gray-400 mt-1">{a.desc}</p>
            </div>
            <span className="text-[10px] font-mono text-gray-400 mt-2">Trigger Ingestion</span>
          </button>
        ))}
      </div>
    </div>
  );
}
