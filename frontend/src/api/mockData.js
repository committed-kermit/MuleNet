export const MOCK_METRICS = {
  prevented_loss_value: 1420500.0,
  detection_lead_time_minutes: 14.2,
  false_challenge_rate_percent: 1.8,
  mule_ring_coverage_percent: 95.0,
  total_scored_actions: 1250,
  flagged_critical_count: 42,
};

export const MOCK_TRANSACTIONS = [
  {
    transaction_id: "TXN-80412",
    timestamp: "2026-09-03T14:32:00Z",
    sender_id: "BANK01_ACC1042",
    receiver_id: "BANK04_ACC9011",
    amount: 48500.0,
    currency: "USD",
    fused_score: 0.91,
    risk_tier: "CRITICAL",
    recommended_action: "HOLD_FOR_REVIEW",
    lenses: {
      sequence_score: 0.94,
      network_score: 0.88,
      context_score: 0.72,
      anomaly_score: 0.81,
    },
    typologies: [
      {
        name: "Rapid Pass-Through",
        evidence: "94% of received funds forwarded in under 8 minutes.",
      },
      {
        name: "Cross-Bank Mule Ring",
        evidence: "Part of a 4-account circular flow across 3 banks.",
      },
    ],
    shap_factors: [
      {
        feature: "setup_to_action_gap",
        impact: 0.38,
        explanation: "Mobile number updated 45s before transfer attempt.",
      },
      {
        feature: "amount_zscore",
        impact: 0.26,
        explanation: "Transfer amount is 6.2x above sender historical average.",
      },
      {
        feature: "device_sharing_flag",
        impact: 0.18,
        explanation: "Shared device fingerprint detected across 3 mule accounts.",
      },
    ],
  },
  {
    transaction_id: "TXN-80411",
    timestamp: "2026-09-03T14:31:45Z",
    sender_id: "BANK02_ACC3318",
    receiver_id: "BANK01_ACC8820",
    amount: 150.0,
    currency: "USD",
    fused_score: 0.05,
    risk_tier: "LOW",
    recommended_action: "ALLOW",
    lenses: {
      sequence_score: 0.04,
      network_score: 0.02,
      context_score: 0.01,
      anomaly_score: 0.03,
    },
    typologies: [],
    shap_factors: [],
  },
  {
    transaction_id: "TXN-80410",
    timestamp: "2026-09-03T14:30:10Z",
    sender_id: "BANK03_ACC7712",
    receiver_id: "BANK05_ACC2049",
    amount: 9800.0,
    currency: "USD",
    fused_score: 0.48,
    risk_tier: "MEDIUM",
    recommended_action: "SOFT_CHALLENGE",
    lenses: {
      sequence_score: 0.52,
      network_score: 0.35,
      context_score: 0.40,
      anomaly_score: 0.42,
    },
    typologies: [
      {
        name: "First-Time High Value Payee",
        evidence: "Transfer to new payee exceeding historical 90-day threshold.",
      },
    ],
    shap_factors: [
      {
        feature: "time_since_payee_added",
        impact: 0.22,
        explanation: "Payee added 4 minutes ago.",
      },
    ],
  },
];

export const MOCK_GRAPH_DATA = {
  nodes: [
    { id: "BANK01_ACC1042", label: "Sender (ATO Victim)", risk_tier: "CRITICAL", is_focus: true },
    { id: "BANK04_ACC9011", label: "Mule Collector", risk_tier: "CRITICAL", is_focus: false },
    { id: "BANK02_ACC5510", label: "Mule Layering", risk_tier: "HIGH", is_focus: false },
    { id: "BANK03_ACC9981", label: "Offshore Exit Hub", risk_tier: "CRITICAL", is_focus: false },
    { id: "BANK01_ACC7720", label: "Legitimate Counterparty", risk_tier: "LOW", is_focus: false },
  ],
  links: [
    { source: "BANK01_ACC1042", target: "BANK04_ACC9011", amount: 48500, gat_attention: 0.91, is_risky: true },
    { source: "BANK04_ACC9011", target: "BANK02_ACC5510", amount: 46000, gat_attention: 0.84, is_risky: true },
    { source: "BANK02_ACC5510", target: "BANK03_ACC9981", amount: 45200, gat_attention: 0.88, is_risky: true },
    { source: "BANK01_ACC1042", target: "BANK01_ACC7720", amount: 250, gat_attention: 0.05, is_risky: false },
  ],
};
