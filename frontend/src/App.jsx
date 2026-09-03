import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import MetricsBar from './components/MetricsBar';
import LiveTransactionFeed from './components/LiveTransactionFeed';
import GraphExplorer from './components/GraphExplorer';
import CaseDossierModal from './components/CaseDossierModal';
import AttackSimulatorPanel from './components/AttackSimulatorPanel';
import SingleActionTester from './components/SingleActionTester';
import { apiClient } from './api/client';
import { MOCK_METRICS, MOCK_TRANSACTIONS, MOCK_GRAPH_DATA } from './api/mockData';

export default function App() {
  const [metrics, setMetrics] = useState(MOCK_METRICS);
  const [transactions, setTransactions] = useState(MOCK_TRANSACTIONS);
  const [graphData, setGraphData] = useState(MOCK_GRAPH_DATA);
  const [selectedTxn, setSelectedTxn] = useState(null);
  const [isStreaming, setIsStreaming] = useState(true);
  const [isTesterOpen, setIsTesterOpen] = useState(false);

  // Load metrics initially
  useEffect(() => {
    apiClient.getMetrics().then(setMetrics);
  }, []);

  // SSE Stream Listener
  useEffect(() => {
    if (!isStreaming) return;

    let eventSource;
    try {
      eventSource = new EventSource('/api/v1/demo/stream');
      eventSource.onmessage = (event) => {
        try {
          const newTxn = JSON.parse(event.data);
          setTransactions((prev) => [newTxn, ...prev.slice(0, 49)]);

          // If transaction is critical, update graph focus
          if (newTxn.risk_tier === 'CRITICAL') {
            apiClient.getEgoGraph(newTxn.sender_id).then(setGraphData);
          }
        } catch (err) {
          console.error('Error parsing stream event:', err);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
      };
    } catch (e) {
      console.warn('SSE stream unavailable:', e);
    }

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [isStreaming]);

  const handleSelectTxn = (txn) => {
    setSelectedTxn(txn);
    apiClient.getEgoGraph(txn.sender_id).then(setGraphData);
  };

  const handleScoreManual = async (payload) => {
    const res = await apiClient.scoreAction(payload);
    setTransactions((prev) => [res, ...prev]);
    setSelectedTxn(res);
    apiClient.getEgoGraph(res.sender_id).then(setGraphData);
  };

  const handleCommit = async (txnId) => {
    await apiClient.commitAction(txnId);
    apiClient.getMetrics().then(setMetrics);
  };

  const handleInjectAttack = async (scenarioType, accountId, amount) => {
    await apiClient.injectAttack(scenarioType, accountId, amount);
  };

  return (
    <div className="min-h-screen bg-background text-gray-100 flex flex-col">
      <Header
        isStreaming={isStreaming}
        onToggleStream={() => setIsStreaming(!isStreaming)}
        onOpenTester={() => setIsTesterOpen(true)}
      />

      <main className="flex-1 space-y-4 pb-8">
        <MetricsBar metrics={metrics} />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 px-6">
          <div className="lg:col-span-5">
            <LiveTransactionFeed
              transactions={transactions}
              selectedTxn={selectedTxn}
              onSelectTxn={handleSelectTxn}
            />
          </div>

          <div className="lg:col-span-7 space-y-4">
            <GraphExplorer
              graphData={graphData}
              selectedNode={selectedTxn?.sender_id}
              onSelectNode={(node) => apiClient.getEgoGraph(node.id).then(setGraphData)}
            />
            <AttackSimulatorPanel onInject={handleInjectAttack} />
          </div>
        </div>
      </main>

      {/* Case Dossier Modal */}
      {selectedTxn && (
        <CaseDossierModal
          txn={selectedTxn}
          onClose={() => setSelectedTxn(null)}
          onCommit={handleCommit}
        />
      )}

      {/* Manual Action Tester */}
      <SingleActionTester
        isOpen={isTesterOpen}
        onClose={() => setIsTesterOpen(false)}
        onScore={handleScoreManual}
      />
    </div>
  );
}
