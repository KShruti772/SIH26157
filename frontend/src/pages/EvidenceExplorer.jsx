import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Database, Clock, ArrowRight, ShieldAlert, FileText, Download, AlertCircle, CheckCircle2, Server, HelpCircle, ArrowLeft } from 'lucide-react';
import api from '../services/api';

const EvidenceExplorer = () => {
  const { findingId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchEvidence = async () => {
      try {
        const res = await api.get(`/evidence/${findingId}`);
        setData(res.data);
      } catch (err) {
        console.error(err);
        setError(err.response?.data?.detail || "Failed to load evidence trace.");
      } finally {
        setLoading(false);
      }
    };
    fetchEvidence();
  }, [findingId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500 mb-4"></div>
        <p>Reconstructing operational evidence trace...</p>
      </div>
    );
  }

  if (error || !data || !data.finding) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-6 text-red-300">
          <h2 className="text-lg font-bold mb-2 flex items-center">
            <AlertCircle className="w-5 h-5 mr-2" /> Evidence Not Found
          </h2>
          <p>{error || "No operational evidence records could be linked to this finding."}</p>
          <Link to="/findings" className="mt-4 inline-block px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 text-sm">
            Return to Findings
          </Link>
        </div>
      </div>
    );
  }

  const { finding, alerts = [], cases = [], assets = [], missing_links = [], evidence_completeness = 1.0 } = data;

  return (
    <div className="max-w-7xl mx-auto py-4">
      <div className="mb-6 flex justify-between items-center">
        <div>
          <Link to={`/findings/${finding.id}`} className="flex items-center text-xs text-slate-400 hover:text-slate-200 mb-2 transition-colors">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Finding Detail
          </Link>
          <h1 className="text-2xl font-bold text-white mb-1">Operational Evidence Explorer</h1>
          <p className="text-slate-400 text-sm">Trace supervisory finding back to authentic ingested SOC telemetry and case records.</p>
        </div>
        <div className="flex items-center space-x-3">
          <div className="bg-slate-800 border border-slate-700 px-4 py-2 rounded-lg text-right">
            <span className="text-xs text-slate-400 block">Evidence Completeness</span>
            <span className="text-lg font-bold text-blue-400 font-mono">
              {(evidence_completeness * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>

      {/* Finding Summary Banner */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 mb-6 shadow-sm">
        <div className="flex items-start">
          <div className="p-3 bg-blue-900/30 rounded border border-blue-800 mr-4 shrink-0">
            <ShieldAlert className="w-6 h-6 text-blue-400" />
          </div>
          <div className="flex-1">
            <div className="flex justify-between items-center mb-1">
              <h2 className="text-lg font-bold text-white">{finding.type}</h2>
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${
                finding.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                finding.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              }`}>
                {finding.severity}
              </span>
            </div>
            <p className="text-slate-400 text-xs mb-3">
              Finding ID: <span className="font-mono text-slate-200">{finding.id}</span> • Entity: <span className="font-mono text-slate-200">{finding.entity_id}</span> • Analytic Rule: <span className="font-mono text-slate-200">{finding.analytic_rule || 'Deterministic Heuristic'}</span>
            </p>
            <div className="bg-slate-900/80 p-3 rounded text-sm text-slate-300 border border-slate-700">
              {finding.description}
            </div>
          </div>
        </div>
      </div>

      {/* Missing Links / Evidence Gaps Alert */}
      {missing_links && missing_links.length > 0 && (
        <div className="bg-orange-950/20 border border-orange-800/40 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-bold text-orange-400 flex items-center mb-2">
            <AlertCircle className="w-4 h-4 mr-2" /> Observed Evidence Gaps & Missing Chain Links
          </h3>
          <ul className="list-disc list-inside space-y-1 text-xs text-orange-200/90 font-mono">
            {missing_links.map((link, idx) => (
              <li key={idx}>{link}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Linked Assets */}
      {assets && assets.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center">
            <Server className="w-4 h-4 mr-2" /> Associated Infrastructure Assets ({assets.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {assets.map(ast => (
              <div key={ast.id} className="bg-slate-800 p-3.5 rounded-lg border border-slate-700">
                <div className="flex justify-between items-center mb-1">
                  <span className="font-mono text-sm font-bold text-white">{ast.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                    ast.criticality === 'Critical' ? 'bg-red-500/20 text-red-400' : 'bg-slate-700 text-slate-300'
                  }`}>
                    {ast.criticality || 'Standard'}
                  </span>
                </div>
                <p className="text-xs text-slate-400">Type: {ast.type || 'Generic Asset'}</p>
                <div className="mt-2 text-xs flex items-center">
                  <span className="text-slate-500 mr-2">Telemetry Status:</span>
                  {ast.has_telemetry ? (
                    <span className="text-green-400 font-medium flex items-center">
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Active Stream
                    </span>
                  ) : (
                    <span className="text-red-400 font-medium flex items-center">
                      <AlertCircle className="w-3.5 h-3.5 mr-1" /> Missing Telemetry
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Underlying Alert Records */}
      <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 flex items-center">
        <Database className="w-4 h-4 mr-2" /> 
        Underlying Records ({alerts.length} Alert(s), {cases.length} Case(s))
      </h3>

      {alerts.length === 0 && cases.length === 0 ? (
        <div className="bg-slate-800 rounded border border-slate-700 p-8 text-center text-slate-400 italic">
          No direct alert records associated. This is a negative space indicator (absence of expected operational evidence).
        </div>
      ) : (
        <div className="space-y-6">
          {alerts.map(alert => (
            <div key={alert.id} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden shadow-sm">
              <div className="bg-slate-900/60 p-4 border-b border-slate-700 flex justify-between items-center">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-slate-400 mr-3" />
                  <div>
                    <span className="font-mono text-sm text-white font-bold">{alert.id}</span>
                    <span className="text-xs text-slate-400 ml-3">Asset: {alert.asset_id || 'Unassigned'}</span>
                  </div>
                </div>
                <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                  alert.severity === 'Critical' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                  alert.severity === 'High' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                  'bg-slate-700 text-slate-300'
                }`}>
                  {alert.severity} • {alert.category}
                </span>
              </div>
              
              <div className="p-6">
                <h4 className="text-xs font-bold text-slate-400 mb-4 uppercase tracking-wider">
                  Operational Chain Sequence (Recorded Timestamps)
                </h4>
                
                <div className="relative pl-6 border-l-2 border-slate-700 space-y-6">
                  {/* Step 1: Alert Generated */}
                  <div className="relative">
                    <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                      <Clock className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="flex justify-between text-sm">
                      <div>
                        <span className="text-white font-medium">Alert Generated in Sensor / SIEM</span>
                        <span className="text-xs text-slate-400 block mt-0.5">Category: {alert.category}</span>
                      </div>
                      <span className="font-mono text-slate-300 text-xs">
                        {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : 'Evidence not available'}
                      </span>
                    </div>
                  </div>
                  
                  {/* Step 2: Acknowledgment */}
                  <div className="relative">
                    <div className={`absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 ${
                      alert.acknowledged ? 'border-green-500' : 'border-slate-600'
                    }`}>
                      <Clock className={`w-4 h-4 ${alert.acknowledged ? 'text-green-400' : 'text-slate-500'}`} />
                    </div>
                    <div className="flex justify-between text-sm">
                      <div>
                        <span className="text-white font-medium">Alert Acknowledgment</span>
                        <span className="text-xs text-slate-400 block mt-0.5">
                          {alert.acknowledged ? 'Acknowledged by operator' : 'Acknowledgment not recorded'}
                        </span>
                      </div>
                      <span className="font-mono text-slate-400 text-xs">
                        {alert.acknowledged ? 'Recorded in console' : 'Evidence not available'}
                      </span>
                    </div>
                  </div>
                  
                  {/* Step 3: Investigation */}
                  <div className="relative">
                    <div className={`absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 ${
                      alert.investigation_started ? 'border-blue-500' : 'border-amber-500'
                    }`}>
                      <Clock className={`w-4 h-4 ${alert.investigation_started ? 'text-blue-400' : 'text-amber-400'}`} />
                    </div>
                    <div className="flex justify-between text-sm">
                      <div>
                        <span className="text-white font-medium">Investigation Stage</span>
                        <span className="text-xs text-slate-400 block mt-0.5">
                          {alert.investigation_started 
                            ? (alert.investigation_duration_mins ? `Recorded duration: ${alert.investigation_duration_mins.toFixed(1)} minutes` : 'Investigation active')
                            : 'Investigation record missing'}
                        </span>
                      </div>
                      <span className="font-mono text-slate-400 text-xs">
                        {alert.investigation_started ? 'Initiated' : 'Evidence not available'}
                      </span>
                    </div>
                  </div>

                  {/* Step 4: Escalation */}
                  <div className={`relative p-3 rounded-lg -ml-2 border ${
                    alert.escalated 
                      ? 'bg-green-500/10 border-green-500/20' 
                      : 'bg-red-500/10 border-red-500/20'
                  }`}>
                    <div className={`absolute -left-[25px] bg-slate-800 p-1 rounded-full border-2 ${
                      alert.escalated ? 'border-green-500' : 'border-red-500'
                    }`}>
                      <Clock className={`w-4 h-4 ${alert.escalated ? 'text-green-500' : 'text-red-500'}`} />
                    </div>
                    <div className="flex justify-between text-sm">
                      <div>
                        <span className="text-white font-medium block">
                          {alert.escalated ? 'Escalated to Higher Tier' : 'Closure Without Escalation'}
                        </span>
                        <span className={`text-xs mt-0.5 block ${alert.escalated ? 'text-green-400' : 'text-red-400'}`}>
                          {alert.escalated 
                            ? 'Incident escalated to Tier-2/3 response team'
                            : 'Operational gap: Critical alert closed without recorded escalation'}
                        </span>
                      </div>
                      <span className="font-mono text-slate-300 text-xs mt-1">
                        {alert.closed_at ? new Date(alert.closed_at).toLocaleString() : (
                          alert.closure_duration_mins ? `Closed in ${alert.closure_duration_mins.toFixed(1)} mins` : 'Evidence not available'
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Linked Cases */}
          {cases.map(c => (
            <div key={c.id} className="bg-slate-800 rounded-lg border border-slate-700 p-5">
              <div className="flex justify-between items-center mb-3">
                <div className="flex items-center">
                  <FileText className="w-4 h-4 text-blue-400 mr-2" />
                  <span className="font-mono text-sm font-bold text-white">Case Record: {c.id}</span>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {c.created_at ? new Date(c.created_at).toLocaleString() : 'Timestamp unavailable'}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs bg-slate-900/50 p-3 rounded border border-slate-700/50">
                <div>
                  <span className="text-slate-500 block uppercase font-medium">Investigator</span>
                  <span className="text-slate-200 mt-0.5 block">{c.investigator || 'Unassigned'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block uppercase font-medium">Investigation Duration</span>
                  <span className="text-slate-200 mt-0.5 block">{c.investigation_duration ? `${c.investigation_duration.toFixed(1)} mins` : 'Not recorded'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block uppercase font-medium">Escalation Status</span>
                  <span className={`mt-0.5 block font-bold ${c.escalation_status ? 'text-green-400' : 'text-slate-400'}`}>
                    {c.escalation_status ? 'Escalated' : 'Not Escalated'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block uppercase font-medium">Closure Reason</span>
                  <span className="text-slate-200 mt-0.5 block">{c.closure_reason || 'Resolved'}</span>
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
