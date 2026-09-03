import React from 'react';
import { Shield, Activity, RefreshCw } from 'lucide-react';

export default function Header({ isStreaming, onToggleStream, onOpenTester }) {
  return (
    <header className="bg-surface border-b border-border px-6 py-4 flex items-center justify-between">
      <div className="flex items-center space-x-3">
        <div className="bg-blue-600/20 p-2 rounded-lg border border-blue-500/30">
          <Shield className="w-6 h-6 text-blue-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white tracking-wide">MuleNet</h1>
          <p className="text-xs text-gray-400">Pre-Commitment AML Risk Intelligence Platform</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <button
          onClick={onOpenTester}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 transition"
        >
          Manual Scoring Test
        </button>

        <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-full">
          <span className={`w-2.5 h-2.5 rounded-full ${isStreaming ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
          <span className="text-xs font-medium text-gray-300">
            {isStreaming ? 'STREAM ACTIVE' : 'STREAM PAUSED'}
          </span>
          <button
            onClick={onToggleStream}
            className="ml-2 text-gray-400 hover:text-white transition"
            title="Toggle Live Stream"
          >
            <Activity className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
