import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Play, Search, ArrowLeft, Database, CheckCircle2, AlertTriangle, XCircle, Clock, Server, Layers } from 'lucide-react';
import api from '../services/api';

const DataPreview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [preview, setPreview] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get(`/upload/${id}/preview`);
        setPreview(res.data);
      } catch (err) {
        console.error("Failed to load upload preview", err);
        setError(err.response?.data?.detail || "Could not retrieve preview for this upload.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleRunAnalysis = async () => {
    try {
      const res = await api.post('/analysis/run');
      navigate(`/analysis/${res.data.analysis_id}`);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500 mb-4"></div>
        <p>Loading normalized dataset preview...</p>
      </div>
    );
  }

  if (error || !preview) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-6 text-red-300">
          <h2 className="text-lg font-bold mb-2 flex items-center">
            <XCircle className="w-5 h-5 mr-2" /> Upload Preview Error
          </h2>
          <p>{error || "Upload record not found."}</p>
          <button 
            onClick={() => navigate('/upload')}
            className="mt-4 px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 text-sm"
          >
            Return to Upload Page
          </button>
        </div>
      </div>
    );
  }

  const rawRows = preview.data || [];
  const filteredRows = rawRows.filter(row => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return Object.values(row).some(v => v !== null && String(v).toLowerCase().includes(term));
  });

  return (
    <div className="max-w-7xl mx-auto flex flex-col h-full py-2">
      {/* Header Bar */}
      <div className="flex justify-between items-center mb-6 shrink-0">
        <div>
          <button 
            onClick={() => navigate('/upload')}
            className="flex items-center text-xs text-slate-400 hover:text-slate-200 mb-2 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Upload
          </button>
          <h1 className="text-2xl font-bold text-white mb-1">
            Data Preview & Normalization Review
          </h1>
          <p className="text-slate-400 text-sm">
            Step 2: Inspect ingested schema and normalized records before supervisory analytics.
          </p>
        </div>
        <button 
          onClick={handleRunAnalysis}
          className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-md font-bold transition-all shadow-lg shadow-blue-600/20 hover:scale-[1.02]"
        >
          <Play className="w-4 h-4 mr-2" fill="currentColor" />
          Run Supervisory Analysis
        </button>
      </div>

      {/* Dataset Metadata Strip */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 mb-6 shadow-sm shrink-0">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
          <div>
            <span className="text-slate-500 uppercase font-semibold block">File</span>
            <span className="text-white font-medium truncate block mt-0.5">{preview.filename}</span>
          </div>
          <div>
            <span className="text-slate-500 uppercase font-semibold block">Dataset Type</span>
            <span className="text-blue-400 font-bold uppercase block mt-0.5">{preview.dataset_type}</span>
          </div>
          <div>
            <span className="text-slate-500 uppercase font-semibold block">Valid / Total</span>
            <span className="text-green-400 font-bold block mt-0.5">
              {preview.records_valid.toLocaleString()} <span className="text-slate-400 font-normal">/ {preview.records_received.toLocaleString()}</span>
            </span>
          </div>
          <div>
            <span className="text-slate-500 uppercase font-semibold block">Entities Detected</span>
            <span className="text-white font-medium block mt-0.5">
              {preview.entities?.length > 0 ? preview.entities.join(", ") : "CSE-001"}
            </span>
          </div>
          <div>
            <span className="text-slate-500 uppercase font-semibold block">Status</span>
            <span className={`inline-block px-2 py-0.5 rounded font-bold uppercase mt-0.5 ${
              preview.status === 'validated' ? 'bg-green-500/20 text-green-400' :
              preview.status === 'validated_with_warnings' ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-red-500/20 text-red-400'
            }`}>
              {preview.status.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 flex flex-col flex-1 overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/80 shrink-0">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search in preview..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-4 py-1.5 bg-slate-900 border border-slate-700 rounded text-sm text-white focus:outline-none focus:border-blue-500 w-72"
            />
          </div>
          <div className="text-xs text-slate-400">
            Showing <span className="text-white font-bold">{filteredRows.length}</span> of {preview.total_preview_records} preview records
          </div>
        </div>
        
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-900/60 sticky top-0 z-10 text-xs uppercase text-slate-400 font-semibold border-b border-slate-700">
              {preview.dataset_type === "alerts" && (
                <tr>
                  <th className="p-3.5">Alert ID</th>
                  <th className="p-3.5">Entity</th>
                  <th className="p-3.5">Timestamp (UTC)</th>
                  <th className="p-3.5">Severity</th>
                  <th className="p-3.5">Category</th>
                  <th className="p-3.5">Asset</th>
                  <th className="p-3.5">Acknowledged</th>
                  <th className="p-3.5">Escalated</th>
                  <th className="p-3.5">Disposition</th>
                </tr>
              )}
              {preview.dataset_type === "assets" && (
                <tr>
                  <th className="p-3.5">Asset ID</th>
                  <th className="p-3.5">Entity</th>
                  <th className="p-3.5">Type</th>
                  <th className="p-3.5">Criticality</th>
                  <th className="p-3.5">Telemetry Monitored</th>
                </tr>
              )}
              {preview.dataset_type === "cases" && (
                <tr>
                  <th className="p-3.5">Case ID</th>
                  <th className="p-3.5">Entity</th>
                  <th className="p-3.5">Alert ID</th>
                  <th className="p-3.5">Created At (UTC)</th>
                  <th className="p-3.5">Investigator</th>
                  <th className="p-3.5">Duration (mins)</th>
                  <th className="p-3.5">Escalated</th>
                  <th className="p-3.5">Closure Reason</th>
                </tr>
              )}
            </thead>
            <tbody className="text-xs divide-y divide-slate-700/50 text-slate-300">
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-slate-400">
                    No matching records found.
                  </td>
                </tr>
              ) : (
                filteredRows.map((row, i) => (
                  <tr key={i} className="hover:bg-slate-750 transition-colors">
                    <td className="p-3.5 font-mono text-blue-400 font-medium">{row.id}</td>
                    <td className="p-3.5">{row.entity_id}</td>
                    
                    {preview.dataset_type === "alerts" && (
                      <>
                        <td className="p-3.5 font-mono text-slate-400">
                          {row.timestamp ? new Date(row.timestamp).toLocaleString() : "-"}
                        </td>
                        <td className="p-3.5">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            row.severity === 'Critical' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                            row.severity === 'High' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20' :
                            row.severity === 'Medium' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                            'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                          }`}>
                            {row.severity}
                          </span>
                        </td>
                        <td className="p-3.5">{row.category || "-"}</td>
                        <td className="p-3.5 font-mono text-slate-400">{row.asset_id || "-"}</td>
                        <td className="p-3.5">{row.acknowledged ? "Yes" : "No"}</td>
                        <td className="p-3.5">
                          <span className={row.escalated ? "text-green-400 font-medium" : "text-slate-400"}>
                            {row.escalated ? "Yes" : "No"}
                          </span>
                        </td>
                        <td className="p-3.5">{row.disposition || "-"}</td>
                      </>
                    )}

                    {preview.dataset_type === "assets" && (
                      <>
                        <td className="p-3.5">{row.type}</td>
                        <td className="p-3.5">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            row.criticality === 'Critical' ? 'bg-red-500/10 text-red-400' :
                            row.criticality === 'High' ? 'bg-orange-500/10 text-orange-400' : 'bg-slate-500/10 text-slate-400'
                          }`}>
                            {row.criticality}
                          </span>
                        </td>
                        <td className="p-3.5">
                          <span className={row.has_telemetry ? "text-green-400" : "text-red-400 font-bold"}>
                            {row.has_telemetry ? "Active (Logging)" : "Missing Telemetry"}
                          </span>
                        </td>
                      </>
                    )}

                    {preview.dataset_type === "cases" && (
                      <>
                        <td className="p-3.5 font-mono text-slate-400">{row.alert_id || "-"}</td>
                        <td className="p-3.5 font-mono text-slate-400">
                          {row.created_at ? new Date(row.created_at).toLocaleString() : "-"}
                        </td>
                        <td className="p-3.5">{row.investigator || "-"}</td>
                        <td className="p-3.5">{row.investigation_duration || 0}</td>
                        <td className="p-3.5">{row.escalation_status ? "Yes" : "No"}</td>
                        <td className="p-3.5">{row.closure_reason || "-"}</td>
                      </>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DataPreview;
