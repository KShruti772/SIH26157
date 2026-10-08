import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Activity, CheckCircle2, ChevronRight } from 'lucide-react';
import api from '../services/api';

const stagesList = [
  "Data validation", 
  "Data normalization", 
  "Entity profiling",
  "Alert analysis", 
  "Case analysis", 
  "Execution gap analysis",
  "Negative-space analysis", 
  "Anomaly detection", 
  "Peer benchmarking",
  "Risk calculation", 
  "Review prioritization"
];

const AnalysisEngine = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/analysis/${id}/status`);
        setStatus(res.data);
        if (res.data.status === 'completed') {
          clearInterval(interval);
        }
      } catch (err) {
        console.error(err);
      }
    }, 1000);
    
    return () => clearInterval(interval);
  }, [id]);

  const currentStageIndex = status ? stagesList.indexOf(status.current_stage) : -1;

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-blue-500/10 mb-6">
          <Activity className={`w-10 h-10 text-blue-500 ${status?.status !== 'completed' ? 'animate-pulse' : ''}`} />
        </div>
        <h1 className="text-3xl font-bold text-white mb-4">
          {status?.status === 'completed' ? 'Analysis Completed Successfully' : 'Running Supervisory Analysis...'}
        </h1>
        <p className="text-slate-400 max-w-2xl mx-auto">
          The engine is processing the uploaded SOC data, detecting execution gaps, negative space, and assessing overall supervisory risk.
        </p>
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 shadow-2xl p-8 mb-8 relative overflow-hidden">
        {/* Progress bar background */}
        <div 
          className="absolute top-0 left-0 h-1 bg-blue-500 transition-all duration-1000 ease-out"
          style={{ width: `${status?.progress || 0}%` }}
        ></div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-6">
          {stagesList.map((stage, i) => {
            const isCompleted = status?.status === 'completed' || i < currentStageIndex;
            const isCurrent = status?.status !== 'completed' && i === currentStageIndex;
            
            return (
              <div key={i} className={`flex items-center p-3 rounded-lg transition-colors ${isCurrent ? 'bg-slate-700/50 border border-slate-600' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center mr-4 shrink-0 ${
                  isCompleted ? 'bg-green-500/20 text-green-500' :
                  isCurrent ? 'bg-blue-500 text-white animate-pulse' :
                  'bg-slate-700 text-slate-500'
                }`}>
                  {isCompleted ? <CheckCircle2 className="w-5 h-5" /> : 
                   isCurrent ? <div className="w-2 h-2 bg-white rounded-full animate-ping"></div> : 
                   <span className="text-xs">{i + 1}</span>}
                </div>
                <span className={`font-medium ${
                  isCompleted ? 'text-slate-200' :
                  isCurrent ? 'text-blue-400' :
                  'text-slate-500'
                }`}>{stage}</span>
              </div>
            );
          })}
        </div>
      </div>

      {status?.status === 'completed' && (
        <div className="flex justify-center animate-fade-in-up">
          <button 
            onClick={() => navigate('/findings')}
            className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 rounded-lg font-bold text-lg shadow-xl shadow-blue-600/20 transition-all hover:scale-105 group"
          >
            View Supervisory Findings
            <ChevronRight className="w-6 h-6 ml-2 transition-transform group-hover:translate-x-1" />
          </button>
        </div>
      )}
    </div>
  );
};

export default AnalysisEngine;
