import axios from 'axios';
import { MOCK_METRICS, MOCK_TRANSACTIONS, MOCK_GRAPH_DATA } from './mockData';

const API_BASE = '/api/v1';

export const apiClient = {
  async getMetrics() {
    try {
      const res = await axios.get(`${API_BASE}/metrics`);
      return res.data;
    } catch {
      return MOCK_METRICS;
    }
  },

  async scoreAction(actionPayload) {
    try {
      const res = await axios.post(`${API_BASE}/score-action`, actionPayload);
      return res.data;
    } catch {
      return MOCK_TRANSACTIONS[0];
    }
  },

  async commitAction(txnId) {
    try {
      const res = await axios.post(`${API_BASE}/commit-action`, { transaction_id: txnId });
      return res.data;
    } catch {
      return { status: 'COMMITTED', transaction_id: txnId, graph_updated: true };
    }
  },

  async getEgoGraph(accountId) {
    try {
      const res = await axios.get(`${API_BASE}/graph/ego/${accountId}`);
      return res.data;
    } catch {
      return MOCK_GRAPH_DATA;
    }
  },

  async injectAttack(scenarioType, accountId, amount) {
    try {
      const res = await axios.post(`${API_BASE}/simulator/inject`, {
        scenario_type: scenarioType,
        account_id: accountId,
        amount: parseFloat(amount) || 49500.0,
      });
      return res.data;
    } catch (e) {
      console.warn("Simulator endpoint offline, using local mock", e);
      return { status: 'INJECTED', scenario_type: scenarioType };
    }
  }
};
