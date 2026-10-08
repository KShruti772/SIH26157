import React, { useState, useEffect } from 'react';
import { Users, BarChart } from 'lucide-react';
import api from '../services/api';

const Benchmarks = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Generate dummy benchmarks for demo purposes since we don't have them in db script
    const mockBenchmarks = [
      { id: 1, entity_id: 'CSE-003', metric: 'Escalation Rate', entity_value: 11.6, peer_median: 84.0, deviation_percent: -72.4, status_label: 'SIGNIFICANT DEVIATION' },
      { id: 2, entity_id: 'CSE-005', metric: 'Monitoring Coverage', entity_value: 65.0, peer_median: 95.0, deviation_percent: -30.0, status_label: 'SIGNIFICANT DEVIATION' },
      { id: 3, entity_id: 'CSE-007', metric: 'Investigation Duration (mins)', entity_value: 4.5, peer_median: 45.0, deviation_percent: -89.0, status_label: 'SIGNIFICANT DEVIATION' },
      { id: 4, entity_id: 'CSE-001', metric: 'Escalation Rate', entity_value: 82.0, peer_median: 84.0, deviation_percent: -2.0, status_label: 'NORMAL' },
      { id: 5, entity_id: 'CSE-002', metric: 'Monitoring Coverage', entity_value: 92.0, peer_median: 95.0, deviation_percent: -3.0, status_label: 'NORMAL' },
    ];
    setBenchmarks(mockBenchmarks);
    setLoading(false);
  }, []);

  if (loading) return <div className="text-white p-8">Loading benchmarks...</div>;

  return (
    <div className="max-w-7xl mx-auto h-full flex flex-col">
      <div className="mb-6 shrink-0">
        <h1 className="text-2xl font-bold text-white mb-2">Peer Benchmarking</h1>
        <p className="text-slate-400">Compare entities against similar peers to identify outliers.</p>
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-900/50 sticky top-0 z-10 text-xs uppercase text-slate-400 font-semibold border-b border-slate-700">
              <tr>
                <th className="p-4">Entity</th>
                <th className="p-4">Metric</th>
                <th className="p-4">Entity Value</th>
                <th className="p-4">Peer Median</th>
                <th className="p-4">Deviation</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="text-sm divide-y divide-slate-700/50 text-slate-300">
              {benchmarks.map((row) => (
                <tr key={row.id} className="hover:bg-slate-700/30 transition-colors">
                  <td className="p-4 font-mono font-medium">{row.entity_id}</td>
                  <td className="p-4">{row.metric}</td>
                  <td className="p-4 font-mono">{row.entity_value}{row.metric.includes('Rate') || row.metric.includes('Coverage') ? '%' : ''}</td>
                  <td className="p-4 font-mono">{row.peer_median}{row.metric.includes('Rate') || row.metric.includes('Coverage') ? '%' : ''}</td>
                  <td className="p-4 font-mono">
                    <span className={row.deviation_percent < -20 ? 'text-red-400' : 'text-slate-300'}>
                      {row.deviation_percent > 0 ? '+' : ''}{row.deviation_percent}%
                    </span>
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      row.status_label === 'SIGNIFICANT DEVIATION' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                      row.status_label === 'WATCH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                      'bg-green-500/20 text-green-400 border border-green-500/30'
                    }`}>
                      {row.status_label}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Benchmarks;
