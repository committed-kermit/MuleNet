import React from 'react';
import { DollarSign, Clock, AlertTriangle, Network } from 'lucide-react';

export default function MetricsBar({ metrics }) {
  const cards = [
    {
      title: 'Prevented Loss Value',
      value: `$${(metrics?.prevented_loss_value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      subtitle: 'Proactively Intercepted',
      icon: DollarSign,
      color: 'text-green-400',
      bg: 'bg-green-500/10',
      border: 'border-green-500/20'
    },
    {
      title: 'Detection Lead Time',
      value: `${metrics?.detection_lead_time_minutes || 0} mins`,
      subtitle: 'Advance Setup Warning',
      icon: Clock,
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/20'
    },
    {
      title: 'False Challenge Rate',
      value: `${metrics?.false_challenge_rate_percent || 0}%`,
      subtitle: 'Legitimate Account Friction',
      icon: AlertTriangle,
      color: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/20'
    },
    {
      title: 'Multi-Party Ring Coverage',
      value: `${metrics?.mule_ring_coverage_percent || 0}%`,
      subtitle: 'Injected Syndicates Flagged',
      icon: Network,
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 px-6 py-4">
      {cards.map((c, i) => {
        const IconComponent = c.icon;
        return (
          <div key={i} className={`bg-surface border ${c.border} rounded-xl p-4 flex items-center justify-between`}>
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{c.title}</p>
              <h3 className="text-2xl font-bold text-white mt-1">{c.value}</h3>
              <p className="text-xs text-gray-400 mt-0.5">{c.subtitle}</p>
            </div>
            <div className={`${c.bg} p-3 rounded-lg border ${c.border}`}>
              <IconComponent className={`w-5 h-5 ${c.color}`} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
