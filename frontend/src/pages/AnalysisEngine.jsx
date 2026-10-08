import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Activity, CheckCircle2, ChevronRight, Database, ShieldCheck, ArrowRight, Layers, Play, AlertCircle, RefreshCw } from 'lucide-react';
import api from '../services/api';

const stagesList = [
  { key: "loading_data", label: "Ingested Records & Profiles", desc: "Loading validated alert, case, and asset records" },
  { key: "reconstructing_evidence", label: "Evidence Reconstruction", desc: "Correlating alerts to cases, assets, and operational logs" },
  { key: "detecting_execution_gaps", label: "Execution Gap Detection", desc: "Evaluating rapid closures, unescalated alerts, and triage gaps" },
  { key: "detecting_negative_space", label: "Negative Space Analysis", desc: "Identifying absent telemetry and dormant critical assets" },
  { key: "detecting_anomalies", label: "Statistical Anomaly Detection", desc: "Computing IQR and median duration outliers" },
  { key: "calculating_benchmarks", label: "Cohort Peer Benchmarking", desc: "Calculating peer medians, averages, and percentile rankings" },
  { key: "calculating_risk", label: "Supervisory Risk Scoring", desc: "Synthesizing 7-factor weighted prioritization scores" },
  { key: "persisting_findings", label: "Database Persistence", desc: "Indexing findings, risk scores, and queue items" },
];

const AnalysisEngine = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [statusData, setStatusData] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!id) return;

    let intervalId;
    const checkStatus = async () => {
      try {
        const res = await api.get(`/analysis/${id}/status`);
        setStatusData(res.data);
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          clearInterval(intervalId);
          setRunning(false);
        } else {
          setRunning(true);
        }
      } catch (err) {
        console.error("Status poll error", err);
        setError("Analysis session not found or expired.");
        clearInterval(intervalId);
        setRunning(false);
      }
    };

    checkStatus();
    intervalId = setInterval(checkStatus, 600);

    return () => clearInterval(intervalId);
  }, [id]);

  const handleTriggerAnalysis = async () => {
    try {
      setRunning(true);
      setError(null);
      const res = await api.post('/analysis/run', {});
      navigate(`/analysis/${res.data.analysis_id}`);
    } catch (err) {
      console.error(err);
      setError("Failed to start analysis session.");
      setRunning(false);
    }
  };

  const progress = statusData?.progress || (statusData?.status === 'completed' ? 100 : 0);
  const currentStage = statusData?.current_stage || '';
  const summary = statusData?.summary;

  return (
    <div className="max-w-4xl mx-auto py-6">
      {/* Title */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-blue-500/10 mb-3 border border-blue-500/20">
          <Layers className="w-7 h-7 text-blue-400" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">
          Supervisory Analytics Engine
        </h1>
        <p className="text-slate-400 max-w-xl mx-auto text-xs leading-relaxed">
          Executes deterministic execution gap detection, negative space analysis, statistical duration anomalies, cohort peer benchmarking, and multi-factor risk scoring.
        </p>
      </div>

      {/* Progress Box if running / active session */}
      {id && statusData && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 mb-8 shadow-xl">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs uppercase font-bold tracking-wider text-slate-400 flex items-center">
              {statusData.status === 'completed' ? (
                <CheckCircle2 className="w-4 h-4 text-green-400 mr-2" />
              ) : (
                <RefreshCw className="w-4 h-4 text-blue-400 mr-2 animate-spin" />
              )}
              Pipeline Execution Status: <span className="text-white ml-1.5 capitalize font-mono">{statusData.status}</span>
            </span>
            <span className="font-mono text-sm font-bold text-blue-400">{progress}%</span>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-900 rounded-full h-2.5 mb-4 overflow-hidden border border-slate-700">
            <div 
              className={`h-2.5 rounded-full transition-all duration-300 ${
                statusData.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'
              }`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>

          <p className="text-xs text-slate-300 mb-6 font-mono">
            {statusData.description || 'Running pipeline stages...'}
          </p>

          {/* Stage Sequence */}
          <div className="space-y-2">
            {stagesList.map((st, i) => {
              const isPast = progress >= ((i + 1) * 12);
              const isCurrent = currentStage === st.key;

              return (
                <div 
                  key={st.key}
                  className={`flex items-center justify-between p-2.5 rounded-lg text-xs transition-colors ${
                    isCurrent ? 'bg-blue-900/30 border border-blue-500/40' :
                    isPast ? 'bg-slate-900/40 border border-slate-800 text-slate-300' :
                    'bg-slate-900/20 border border-slate-900 text-slate-500'
                  }`}
                >
                  <div className="flex items-center">
                    {isPast || statusData.status === 'completed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-green-400 mr-2.5 shrink-0" />
                    ) : (
                      <div className={`w-2 h-2 rounded-full mr-3 shrink-0 ${isCurrent ? 'bg-blue-400 animate-ping' : 'bg-slate-600'}`} />
                    )}
                    <div>
                      <span className={`font-semibold ${isCurrent ? 'text-blue-300' : (isPast ? 'text-white' : 'text-slate-500')}`}>
                        {st.label}
                      </span>
                      <span className="text-[11px] text-slate-400 block mt-0.5">{st.desc}</span>
                    </div>
                  </div>
                  <span className="font-mono text-[10px] uppercase font-bold">
                    {statusData.status === 'completed' || isPast ? 'Done' : (isCurrent ? 'Running' : 'Pending')}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Summary Box when completed */}
          {summary && (
            <div className="mt-6 p-4 bg-slate-900/80 rounded-lg border border-slate-700">
              <h3 className="text-xs font-bold uppercase text-slate-300 mb-3 tracking-wider">
                Analysis Summary & Findings Discovered
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-xs">
                <div className="p-2.5 bg-slate-800 rounded border border-slate-700">
                  <span className="text-slate-400 block text-[10px] uppercase">Execution Gaps</span>
                  <span className="text-lg font-bold text-red-400 font-mono mt-0.5 block">
                    {summary.categories?.execution_gaps ?? 0}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-800 rounded border border-slate-700">
                  <span className="text-slate-400 block text-[10px] uppercase">Negative Space</span>
                  <span className="text-lg font-bold text-orange-400 font-mono mt-0.5 block">
                    {summary.categories?.negative_space ?? 0}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-800 rounded border border-slate-700">
                  <span className="text-slate-400 block text-[10px] uppercase">Anomalies</span>
                  <span className="text-lg font-bold text-yellow-400 font-mono mt-0.5 block">
                    {summary.categories?.anomalies ?? 0}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-800 rounded border border-slate-700">
                  <span className="text-slate-400 block text-[10px] uppercase">Peer Deviations</span>
                  <span className="text-lg font-bold text-blue-400 font-mono mt-0.5 block">
                    {summary.categories?.peer_deviations ?? 0}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-center space-x-4">
        {!id && (
          <button 
            onClick={handleTriggerAnalysis}
            disabled={running}
            className="flex items-center bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-3 rounded-lg font-bold shadow-xl shadow-blue-600/20 transition-all hover:scale-105 text-sm"
          >
            <Play className="w-4 h-4 mr-2" fill="currentColor" />
            Run Supervisory Analytics Across All Ingested Data
          </button>
        )}
        <button 
          onClick={() => navigate('/findings')}
          className="flex items-center bg-slate-700 hover:bg-slate-600 text-white px-6 py-3 rounded-lg font-bold shadow-md transition-all text-sm"
        >
          View All Findings
          <ChevronRight className="w-4 h-4 ml-2" />
        </button>
        <button 
          onClick={() => navigate('/benchmarks')}
          className="flex items-center border border-slate-600 hover:bg-slate-800 text-slate-300 px-6 py-3 rounded-lg font-medium transition-colors text-sm"
        >
          Peer Benchmarks
        </button>
      </div>
    </div>
  );
};

export default AnalysisEngine;
