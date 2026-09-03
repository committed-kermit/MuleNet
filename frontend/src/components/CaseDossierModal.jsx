import React from 'react';
import { X, ShieldAlert, CheckCircle2, AlertOctagon, FileText } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function CaseDossierModal({ txn, onClose, onCommit }) {
  if (!txn) return null;

  const shapData = (txn.shap_factors || []).map((f) => ({
    name: f.feature,
    impact: Math.abs(f.impact),
    rawImpact: f.impact,
    explanation: f.explanation,
  }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-card">
          <div className="flex items-center space-x-3">
            <div className="bg-red-500/20 p-2 rounded-lg border border-red-500/30">
              <ShieldAlert className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-white">Forensic Case Dossier</h3>
                <span className="text-xs font-mono text-gray-400">[{txn.transaction_id}]</span>
              </div>
              <p className="text-xs text-gray-400">
                Pre-Commitment AML Risk Scoring & Decision Breakdown
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
          {/* Top Score Matrix */}
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-card p-3 rounded-lg border border-border text-center">
              <p className="text-[10px] uppercase text-gray-400">Fused Risk Score</p>
              <p className="text-xl font-bold text-red-400 mt-0.5">{(txn.fused_score || 0).toFixed(2)}</p>
              <p className="text-[10px] text-gray-500">{txn.risk_tier}</p>
            </div>
            <div className="bg-card p-3 rounded-lg border border-border text-center">
              <p className="text-[10px] uppercase text-gray-400">Sequence Lens</p>
              <p className="text-xl font-bold text-blue-400 mt-0.5">{(txn.lenses?.sequence_score || 0).toFixed(2)}</p>
              <p className="text-[10px] text-gray-500">Lifecycle Gap</p>
            </div>
            <div className="bg-card p-3 rounded-lg border border-border text-center">
              <p className="text-[10px] uppercase text-gray-400">Network Lens</p>
              <p className="text-xl font-bold text-purple-400 mt-0.5">{(txn.lenses?.network_score || 0).toFixed(2)}</p>
              <p className="text-[10px] text-gray-500">GAT Attention</p>
            </div>
            <div className="bg-card p-3 rounded-lg border border-border text-center">
              <p className="text-[10px] uppercase text-gray-400">Context Lens</p>
              <p className="text-xl font-bold text-yellow-400 mt-0.5">{(txn.lenses?.context_score || 0).toFixed(2)}</p>
              <p className="text-[10px] text-gray-500">Payload Rules</p>
            </div>
          </div>

          {/* Plain-Language Explanations */}
          <div>
            <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
              <FileText className="w-3.5 h-3.5 text-blue-400" />
              <span>Plain-Language Forensic Evidence</span>
            </h4>
            <div className="bg-card/70 border border-border rounded-xl p-3.5 space-y-2">
              {txn.shap_factors?.map((f, i) => (
                <div key={i} className="flex items-start space-x-2 text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 mt-1.5 shrink-0" />
                  <span className="text-gray-200">{f.explanation}</span>
                </div>
              ))}
              {txn.typologies?.map((t, i) => (
                <div key={i} className="flex items-start space-x-2 text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 mt-1.5 shrink-0" />
                  <span className="text-gray-200">
                    <strong className="text-yellow-300">{t.name}:</strong> {t.evidence}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* SHAP Feature Contribution Chart */}
          {shapData.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
                SHAP Feature Impact Attribution
              </h4>
              <div className="bg-card/70 border border-border rounded-xl p-3 h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={shapData} layout="vertical" margin={{ left: 40, right: 20, top: 10, bottom: 10 }}>
                    <XAxis type="number" domain={[0, 0.6]} stroke="#6B7280" tick={{ fontSize: 10 }} />
                    <YAxis dataKey="name" type="category" stroke="#9CA3AF" tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', fontSize: '11px' }} />
                    <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                      {shapData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={index === 0 ? '#EF4444' : '#3B82F6'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-border bg-card/80 flex items-center justify-between">
          <div className="text-xs text-gray-400">
            Recommended Action: <strong className="text-red-300">{txn.recommended_action}</strong>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition"
            >
              Dismiss
            </button>
            <button
              onClick={() => {
                onCommit(txn.transaction_id);
                onClose();
              }}
              className="px-4 py-2 text-xs font-medium rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition"
            >
              Commit Transaction
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
