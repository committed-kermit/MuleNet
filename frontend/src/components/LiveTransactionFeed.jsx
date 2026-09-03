import React from 'react';
import { ArrowRight, AlertCircle, CheckCircle, ShieldAlert } from 'lucide-react';

const TIER_STYLES = {
  LOW: {
    badge: 'bg-green-500/10 text-green-400 border-green-500/20',
    bar: 'bg-green-500',
    label: 'ALLOW',
  },
  MEDIUM: {
    badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    bar: 'bg-yellow-500',
    label: 'SOFT CHALLENGE',
  },
  HIGH: {
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    bar: 'bg-orange-500',
    label: 'STEP-UP AUTH',
  },
  CRITICAL: {
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
    bar: 'bg-red-500',
    label: 'HOLD FOR REVIEW',
  },
};

export default function LiveTransactionFeed({ transactions, selectedTxn, onSelectTxn }) {
  return (
    <div className="bg-surface border border-border rounded-xl flex flex-col h-[580px] overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex items-center justify-between bg-card/50">
        <div className="flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Live Pre-Commitment Feed</h2>
        </div>
        <span className="text-xs text-gray-400">{transactions.length} Scored Events</span>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-border/60">
        {transactions.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-500">
            Waiting for live transaction stream events...
          </div>
        ) : (
          transactions.map((t) => {
            const style = TIER_STYLES[t.risk_tier] || TIER_STYLES.LOW;
            const isSelected = selectedTxn?.transaction_id === t.transaction_id;

            return (
              <div
                key={t.transaction_id}
                onClick={() => onSelectTxn(t)}
                className={`p-3.5 hover:bg-card/70 transition cursor-pointer flex items-center justify-between ${
                  isSelected ? 'bg-blue-900/20 border-l-4 border-l-blue-500' : ''
                }`}
              >
                <div className="flex items-center space-x-3">
                  <div className="text-left">
                    <div className="flex items-center space-x-1.5 text-xs text-gray-300">
                      <span className="font-mono font-medium text-blue-300">{t.sender_id}</span>
                      <ArrowRight className="w-3 h-3 text-gray-500" />
                      <span className="font-mono font-medium text-purple-300">{t.receiver_id}</span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1 flex items-center space-x-2">
                      <span className="font-mono font-semibold text-white">
                        ${t.amount?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                      <span>•</span>
                      <span>{t.timestamp?.split('T')[1]?.split('.')[0] || '14:32:00'}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <div className="text-right">
                    <span className={`inline-block px-2.5 py-0.5 rounded text-[10px] font-bold tracking-wider border ${style.badge}`}>
                      {t.risk_tier} ({(t.fused_score || 0).toFixed(2)})
                    </span>
                    <div className="text-[11px] font-medium text-gray-400 mt-0.5">
                      {style.label}
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
