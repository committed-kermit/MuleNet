import React, { useState } from 'react';
import { X, Play } from 'lucide-react';

export default function SingleActionTester({ isOpen, onClose, onScore }) {
  const [accountId, setAccountId] = useState('BANK01_ACC1042');
  const [counterpartyId, setCounterpartyId] = useState('BANK04_ACC9011');
  const [amount, setAmount] = useState('48500');
  const [currency, setCurrency] = useState('USD');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onScore({
      account_id: accountId,
      counterparty_id: counterpartyId,
      amount: parseFloat(amount),
      currency: currency,
      action_type: 'transfer',
      timestamp: new Date().toISOString(),
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-surface border border-border rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-card">
          <h3 className="text-sm font-bold text-white">Manual Pre-Commitment Scoring Tester</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1">Sender Account ID</label>
            <input
              type="text"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1">Counterparty Account ID</label>
            <input
              type="text"
              value={counterpartyId}
              onChange={(e) => setCounterpartyId(e.target.value)}
              className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Amount</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Currency</label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-card border border-border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="INR">INR</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            className="w-full mt-4 bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg text-xs flex items-center justify-center space-x-1.5 transition"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>Score Action (Pre-Commitment)</span>
          </button>
        </form>
      </div>
    </div>
  );
}
