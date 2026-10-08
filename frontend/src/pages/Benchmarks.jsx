import React, { useState, useEffect } from 'react';
import { Users, BarChart, AlertTriangle, ShieldCheck, HelpCircle } from 'lucide-react';
import api from '../services/api';

const Benchmarks = () => {
  const [benchmarks, setBenchmarks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchBenchmarks = async () => {
      try {
        const res = await api.get('/benchmarks');
        setBenchmarks(res.data || []);
      } catch (err) {
        console.error("Failed to load benchmarks", err);
        setError("Could not retrieve cohort benchmarks from supervisory engine.");
      } finally {
        setLoading(false);
      }
    };
    fetchBenchmarks();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500 mb-4"></div>
        <p>Calculating cohort peer benchmarks...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto h-full flex flex-col py-2">
      <div className="mb-6 shrink-0">
        <h1 className="text-2xl font-bold text-white mb-1">Cohort Peer Benchmarking</h1>
        <p className="text-slate-400 text-sm">
          Deterministic statistical comparison across peer Critical Sector Entities (CSEs) to highlight operational deviations.
        </p>
        <p className="text-xs text-slate-500 mt-1 italic">
          Disclaimer: Peer deviation is a supervisory prioritization signal for human review and does not constitute statutory non-compliance.
        </p>
      </div>

      {benchmarks.length === 0 ? (
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-8 text-center text-slate-400">
          <HelpCircle className="w-10 h-10 text-slate-500 mx-auto mb-3" />
          <h3 className="text-lg font-bold text-white mb-1">Insufficient Peer Sample</h3>
          <p className="text-sm max-w-md mx-auto">
            Cohort peer benchmarking requires at least 2 entities in the database or active dataset upload to calculate meaningful medians.
          </p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden flex flex-col shadow-sm">
          <div className="flex-1 overflow-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-900/60 sticky top-0 z-10 text-xs uppercase text-slate-400 font-semibold border-b border-slate-700">
                <tr>
                  <th className="p-4">Entity</th>
                  <th className="p-4">Metric</th>
                  <th className="p-4">Entity Value</th>
                  <th className="p-4">Peer Median</th>
                  <th className="p-4">Peer Average</th>
                  <th className="p-4">Cohort Percentile</th>
                  <th className="p-4">Deviation</th>
                  <th className="p-4">Supervisory Status</th>
                </tr>
              </thead>
              <tbody className="text-sm divide-y divide-slate-700/50 text-slate-300">
                {benchmarks.map((row, idx) => {
                  const isRate = row.metric.includes('Rate') || row.metric.includes('Coverage');
                  const isDuration = row.metric.includes('mins') || row.metric.includes('Duration');
                  const unit = isRate ? '%' : (isDuration ? 'm' : '');

                  return (
                    <tr key={row.id || idx} className="hover:bg-slate-700/30 transition-colors">
                      <td className="p-4 font-mono font-bold text-white">{row.entity_id}</td>
                      <td className="p-4 font-medium">{row.metric}</td>
                      <td className="p-4 font-mono text-slate-200">
                        {row.entity_value}{unit}
                      </td>
                      <td className="p-4 font-mono text-slate-400">
                        {row.peer_median}{unit}
                      </td>
                      <td className="p-4 font-mono text-slate-400">
                        {row.peer_average}{unit}
                      </td>
                      <td className="p-4 font-mono text-slate-300">
                        {row.percentile !== undefined ? `${row.percentile}%` : '—'}
                      </td>
                      <td className="p-4 font-mono">
                        <span className={
                          row.deviation_percent < -20 ? 'text-red-400 font-semibold' :
                          row.deviation_percent > 20 ? 'text-amber-400' : 'text-slate-300'
                        }>
                          {row.deviation_percent > 0 ? '+' : ''}{row.deviation_percent}%
                        </span>
                      </td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                          row.status_label === 'SIGNIFICANT DEVIATION' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                          row.status_label === 'WATCH' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                          'bg-green-500/20 text-green-400 border border-green-500/30'
                        }`}>
                          {row.status_label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default Benchmarks;
