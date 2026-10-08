import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Database, Clock, ArrowRight, ShieldAlert, FileText, Download } from 'lucide-react';
import api from '../services/api';

const EvidenceExplorer = () => {
  const { findingId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvidence = async () => {
      try {
        const res = await api.get(`/evidence/${findingId}`);
        setData(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEvidence();
  }, [findingId]);

  if (loading) return <div className="text-white p-8">Loading evidence...</div>;
  if (!data || !data.finding) return <div className="text-white p-8">Evidence not found.</div>;

  const { finding, alerts, cases } = data;

  return (
    <div className="max-w-7xl mx-auto py-4">
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Evidence Explorer</h1>
          <p className="text-slate-400">Trace analytical findings back to underlying SOC data.</p>
        </div>
        <button className="flex items-center text-sm font-medium text-slate-200 bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded transition-colors">
          <Download className="w-4 h-4 mr-2" /> Export Evidence
        </button>
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 mb-6">
        <div className="flex items-start">
          <div className="p-3 bg-blue-900/30 rounded border border-blue-800 mr-4">
            <ShieldAlert className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white mb-1">{finding.type}</h2>
            <p className="text-slate-400 text-sm mb-3">Finding ID: {finding.id} • Entity: {finding.entity_id}</p>
            <div className="bg-slate-900 p-3 rounded text-sm text-slate-300 border border-slate-700">
              {finding.rationale}
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-lg font-medium text-white mb-4 flex items-center">
        <Database className="w-5 h-5 mr-2 text-slate-400" /> 
        Underlying Records ({alerts.length} Alerts, {cases.length} Cases)
      </h3>

      {alerts.length === 0 && cases.length === 0 ? (
        <div className="bg-slate-800 rounded border border-slate-700 p-8 text-center text-slate-400 italic">
          No direct records associated. This is likely a negative space indicator (absence of expected evidence).
        </div>
      ) : (
        <div className="space-y-6">
          {alerts.map(alert => (
            <div key={alert.id} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
              <div className="bg-slate-900/50 p-4 border-b border-slate-700 flex justify-between items-center">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-slate-400 mr-3" />
                  <span className="font-mono text-sm text-white">{alert.id}</span>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  alert.severity === 'Critical' ? 'bg-red-500/20 text-red-400' : 'bg-slate-700 text-slate-300'
                }`}>
                  {alert.severity} • {alert.category}
                </span>
              </div>
              
              <div className="p-6">
                <h4 className="text-sm font-bold text-slate-400 mb-4 uppercase">Timeline Sequence</h4>
                
                <div className="relative pl-6 border-l-2 border-slate-700 space-y-6">
                  <div className="relative">
                    <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                      <Clock className="w-4 h-4 text-slate-400" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white">Alert Generated</span>
                      <span className="font-mono text-slate-500">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                    </div>
                  </div>
                  
                  <div className="relative">
                    <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                      <Clock className="w-4 h-4 text-slate-400" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white">Alert Acknowledged</span>
                      <span className="font-mono text-slate-500">
                        {new Date(new Date(alert.timestamp).getTime() + 2 * 60000).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                  
                  <div className="relative">
                    <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                      <Clock className="w-4 h-4 text-slate-400" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white">Investigation Started</span>
                      <span className="font-mono text-slate-500">
                        {new Date(new Date(alert.timestamp).getTime() + 3 * 60000).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>

                  <div className="relative">
                    <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                      <Clock className="w-4 h-4 text-slate-400" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-white">Investigation Completed</span>
                      <span className="font-mono text-slate-500">
                        {new Date(new Date(alert.timestamp).getTime() + (3 + alert.investigation_duration_mins) * 60000).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>

                  <div className="relative p-3 bg-red-500/10 border border-red-500/20 rounded-lg -ml-2">
                    <div className="absolute -left-[25px] bg-slate-800 p-1 rounded-full border-2 border-red-500">
                      <Clock className="w-4 h-4 text-red-500" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <div>
                        <span className="text-white font-medium block">Case Closed - No Escalation</span>
                        <span className="text-xs text-red-400 mt-1 block">Highlight: Closed without expected escalation behavior.</span>
                      </div>
                      <span className="font-mono text-slate-500 mt-1">
                        {new Date(new Date(alert.timestamp).getTime() + (3 + alert.closure_duration_mins) * 60000).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EvidenceExplorer;
