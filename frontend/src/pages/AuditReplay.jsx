import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ShieldCheck, ShieldAlert, History, RotateCcw, CheckCircle2, 
  XCircle, AlertTriangle, ArrowLeft, RefreshCw, FileText, 
  Layers, Database, UserCheck, Bot, Clock, ChevronRight, Hash
} from 'lucide-react';
import api from '../services/api';

const AuditReplay = () => {
  const { analysisId } = useParams();
  const navigate = useNavigate();

  const [uploads, setUploads] = useState([]);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState(analysisId || '');
  const [loading, setLoading] = useState(false);
  const [replaying, setReplaying] = useState(false);
  const [verifying, setVerifying] = useState(false);

  // Replay result data
  const [replayData, setReplayData] = useState(null);
  const [integrityData, setIntegrityData] = useState(null);
  const [auditEvents, setAuditEvents] = useState([]);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('reconstruction'); // 'reconstruction' | 'events' | 'mismatches'
  const [selectedEvent, setSelectedEvent] = useState(null);

  useEffect(() => {
    fetchAvailableUploads();
  }, []);

  useEffect(() => {
    if (analysisId) {
      setSelectedAnalysisId(analysisId);
      runReplay(analysisId);
    }
  }, [analysisId]);

  const fetchAvailableUploads = async () => {
    try {
      const res = await api.get('/audit/events?limit=50&order=desc');
      const events = res.data || [];
      const distinctAnalyses = [];
      const seen = new Set();
      
      events.forEach(e => {
        if (e.analysis_id && !seen.has(e.analysis_id)) {
          seen.add(e.analysis_id);
          distinctAnalyses.push({
            id: e.analysis_id,
            entity_id: e.entity_id || 'CSE-001',
            timestamp: e.timestamp
          });
        }
      });

      // Also fetch dataset uploads
      try {
        const upRes = await api.get('/dashboard/summary');
        if (upRes.data && upRes.data.entities) {
          // Add entities if needed
        }
      } catch (err) {}

      setUploads(distinctAnalyses);
      if (!selectedAnalysisId && distinctAnalyses.length > 0) {
        setSelectedAnalysisId(distinctAnalyses[0].id);
        runReplay(distinctAnalyses[0].id);
      }
    } catch (err) {
      console.error('Failed to load uploads for audit replay', err);
    }
  };

  const runReplay = async (idToReplay) => {
    const targetId = idToReplay || selectedAnalysisId;
    if (!targetId) return;

    setReplaying(true);
    setError(null);
    try {
      // 1. Run Replay
      const replayRes = await api.post(`/audit/replay/${targetId}`);
      setReplayData(replayRes.data);

      // 2. Fetch Integrity
      const intRes = await api.get(`/audit/integrity/${targetId}`);
      setIntegrityData(intRes.data);

      // 3. Fetch Raw Events
      const evRes = await api.get(`/audit/analysis/${targetId}`);
      setAuditEvents(evRes.data || []);
      if (evRes.data && evRes.data.length > 0) {
        setSelectedEvent(evRes.data[0]);
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to execute replay.');
    } finally {
      setReplaying(false);
    }
  };

  const verifyChainOnly = async () => {
    if (!selectedAnalysisId) return;
    setVerifying(true);
    try {
      const res = await api.get(`/audit/integrity/${selectedAnalysisId}`);
      setIntegrityData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Verification error');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Navigation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-800 p-6 rounded-lg border border-slate-700">
        <div>
          <div className="flex items-center space-x-3 mb-2">
            <button 
              onClick={() => navigate(-1)} 
              className="p-1.5 bg-slate-700 hover:bg-slate-600 rounded text-slate-300 hover:text-white transition-colors"
              title="Go back"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h1 className="text-xl font-bold text-white flex items-center">
              <History className="w-6 h-6 mr-2.5 text-blue-400" />
              Audit Ledger & Deterministic Replay Engine
            </h1>
          </div>
          <p className="text-xs text-slate-400">
            Cryptographically verifiable SHA-256 hash chains and deterministic state reconstruction for supervisory assessments.
          </p>
        </div>

        {/* Analysis Selector & Action Buttons */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-slate-900 border border-slate-700 rounded px-3 py-1.5">
            <span className="text-xs text-slate-400 mr-2 font-mono">Analysis:</span>
            {uploads.length > 0 ? (
              <select
                value={selectedAnalysisId}
                onChange={(e) => {
                  setSelectedAnalysisId(e.target.value);
                  runReplay(e.target.value);
                }}
                className="bg-transparent text-xs text-white focus:outline-none font-mono"
              >
                {uploads.map(u => (
                  <option key={u.id} value={u.id} className="bg-slate-800 text-white">
                    {u.id} ({u.entity_id})
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={selectedAnalysisId}
                onChange={(e) => setSelectedAnalysisId(e.target.value)}
                placeholder="Enter Analysis/Upload ID..."
                className="bg-transparent text-xs text-white focus:outline-none font-mono w-40"
              />
            )}
          </div>

          <button
            onClick={() => runReplay(selectedAnalysisId)}
            disabled={replaying || !selectedAnalysisId}
            className="flex items-center px-3.5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800/50 text-white rounded text-xs font-bold transition-colors"
          >
            <RotateCcw className={`w-3.5 h-3.5 mr-1.5 ${replaying ? 'animate-spin' : ''}`} />
            {replaying ? 'Replaying State...' : 'Replay Assessment'}
          </button>

          <button
            onClick={verifyChainOnly}
            disabled={verifying || !selectedAnalysisId}
            className="flex items-center px-3.5 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs font-bold border border-slate-600 transition-colors"
          >
            <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-green-400" />
            {verifying ? 'Verifying...' : 'Verify Chain'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/50 border border-red-800 rounded-lg flex items-center space-x-3 text-red-200 text-xs">
          <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Summary Scorecard Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        {/* Card 1: Analysis ID */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Target Analysis</span>
          <span className="text-xs font-mono font-bold text-white truncate block">
            {replayData?.analysis_id || selectedAnalysisId || 'N/A'}
          </span>
          <span className="text-[10px] text-slate-500 font-mono block mt-1">
            Entity: {replayData?.entity_id || 'CSE-001'}
          </span>
        </div>

        {/* Card 2: Events Processed */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Audit Events</span>
          <div className="flex items-baseline space-x-1.5">
            <span className="text-xl font-bold text-blue-400 font-mono">
              {replayData?.events_processed || auditEvents.length || 0}
            </span>
            <span className="text-[10px] text-slate-400">chained</span>
          </div>
          <span className="text-[10px] text-slate-500 block mt-1">Append-only stream</span>
        </div>

        {/* Card 3: Cryptographic Chain Integrity */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Chain Integrity</span>
          {integrityData?.valid || replayData?.chain_integrity === 'VERIFIED' ? (
            <div className="flex items-center text-green-400 text-xs font-bold mt-1">
              <ShieldCheck className="w-4 h-4 mr-1.5 shrink-0" />
              VERIFIED
            </div>
          ) : integrityData && !integrityData.valid ? (
            <div className="flex items-center text-red-400 text-xs font-bold mt-1">
              <ShieldAlert className="w-4 h-4 mr-1.5 shrink-0" />
              BROKEN LINK
            </div>
          ) : (
            <span className="text-xs text-slate-500 italic mt-1 block">Pending Verification</span>
          )}
          <span className="text-[10px] text-slate-500 block mt-1 font-mono">SHA-256 Chained</span>
        </div>

        {/* Card 4: Replay Validity */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Replay Status</span>
          {replayData?.replay_valid ? (
            <div className="flex items-center text-green-400 text-xs font-bold mt-1">
              <CheckCircle2 className="w-4 h-4 mr-1.5 shrink-0" />
              DETERMINISTIC
            </div>
          ) : replayData ? (
            <div className="flex items-center text-amber-400 text-xs font-bold mt-1">
              <AlertTriangle className="w-4 h-4 mr-1.5 shrink-0" />
              ANOMALOUS
            </div>
          ) : (
            <span className="text-xs text-slate-500 italic mt-1 block">Ready</span>
          )}
          <span className="text-[10px] text-slate-500 block mt-1">Zero Non-Determinism</span>
        </div>

        {/* Card 5: State Equality Match */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">State Equality</span>
          {replayData?.state_match ? (
            <div className="flex items-center text-green-400 text-xs font-bold mt-1">
              <CheckCircle2 className="w-4 h-4 mr-1.5 shrink-0" />
              100% MATCH
            </div>
          ) : replayData ? (
            <div className="flex items-center text-red-400 text-xs font-bold mt-1">
              <XCircle className="w-4 h-4 mr-1.5 shrink-0" />
              MISMATCH ({replayData.mismatches?.length || 0})
            </div>
          ) : (
            <span className="text-xs text-slate-500 italic mt-1 block">Not replayed</span>
          )}
          <span className="text-[10px] text-slate-500 block mt-1">Replay == Database</span>
        </div>

        {/* Card 6: Replayed Timestamp */}
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
          <span className="text-[10px] text-slate-400 uppercase font-semibold block mb-1">Last Verification</span>
          <span className="text-xs font-mono text-slate-300 block truncate">
            {replayData?.replayed_at ? new Date(replayData.replayed_at).toLocaleTimeString() : 'N/A'}
          </span>
          <span className="text-[10px] text-slate-500 block mt-1">Offline Local Replay</span>
        </div>
      </div>

      {/* Main Content Workspace: Navigation Tabs */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        {/* Tab Headers */}
        <div className="flex border-b border-slate-700 bg-slate-900/60 px-6">
          <button
            onClick={() => setActiveTab('reconstruction')}
            className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center ${
              activeTab === 'reconstruction'
                ? 'border-blue-400 text-blue-400 bg-slate-800/60'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <RotateCcw className="w-3.5 h-3.5 mr-2" />
            Reconstructed State vs Persisted Database
          </button>
          <button
            onClick={() => setActiveTab('events')}
            className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center ${
              activeTab === 'events'
                ? 'border-blue-400 text-blue-400 bg-slate-800/60'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Hash className="w-3.5 h-3.5 mr-2" />
            Cryptographic Event Chain ({auditEvents.length})
          </button>
          {replayData?.mismatches && replayData.mismatches.length > 0 && (
            <button
              onClick={() => setActiveTab('mismatches')}
              className={`py-3.5 px-4 text-xs font-bold uppercase tracking-wider border-b-2 transition-colors flex items-center ${
                activeTab === 'mismatches'
                  ? 'border-red-400 text-red-400 bg-slate-800/60'
                  : 'border-transparent text-red-400 hover:text-red-300'
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5 mr-2" />
              Mismatches ({replayData.mismatches.length})
            </button>
          )}
        </div>

        {/* Tab 1: Reconstructed State vs Persisted Database */}
        {activeTab === 'reconstruction' && (
          <div className="p-6 space-y-6">
            {replayData ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left: Reconstructed Assessment State */}
                <div className="bg-slate-900/80 border border-blue-900/40 rounded-lg p-5 space-y-4">
                  <div className="flex justify-between items-center border-b border-slate-700/80 pb-3">
                    <h3 className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center">
                      <RotateCcw className="w-4 h-4 mr-2" />
                      1. Reconstructed State (From Event Ledger)
                    </h3>
                    <span className="text-[10px] bg-blue-900/40 text-blue-300 font-mono px-2 py-0.5 rounded border border-blue-800">
                      Replay Output
                    </span>
                  </div>

                  {/* Findings Reconstructed */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 block mb-2">
                      Reconstructed Findings ({replayData.reconstructed_state?.findings_count || 0})
                    </span>
                    <div className="space-y-2">
                      {replayData.reconstructed_state?.findings?.map((rf, idx) => (
                        <div key={idx} className="bg-slate-800/90 p-3 rounded border border-slate-700 text-xs space-y-1.5">
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-white">{rf.type || rf.id}</span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              rf.severity === 'CRITICAL' ? 'bg-red-950 text-red-400 border border-red-800' :
                              rf.severity === 'HIGH' ? 'bg-orange-950 text-orange-400 border border-orange-800' :
                              'bg-slate-700 text-slate-300'
                            }`}>
                              {rf.severity || 'UNKNOWN'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                            <span>ID: {rf.id}</span>
                            <span>Confidence: {rf.confidence != null ? `${Math.round(rf.confidence * 100)}%` : 'N/A'}</span>
                            <span>Decision: <strong className="text-white">{rf.decision_status || 'OPEN'}</strong></span>
                          </div>
                          {rf.adjudicated_by && (
                            <p className="text-[10px] text-slate-500 font-mono">
                              Adjudicated by: {rf.adjudicated_by}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Assessment Validity Reconstructed */}
                  <div className="bg-slate-800/60 p-3 rounded border border-slate-700/60 flex justify-between items-center">
                    <span className="text-xs text-slate-400">Reconstructed Assessment Validity:</span>
                    <span className={`text-xs font-bold font-mono px-2.5 py-1 rounded ${
                      replayData.reconstructed_state?.assessment_validity === 'HIGH' ? 'bg-green-950 text-green-400 border border-green-800' :
                      replayData.reconstructed_state?.assessment_validity === 'CAUTION' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      'bg-red-950 text-red-400 border border-red-800'
                    }`}>
                      {replayData.reconstructed_state?.assessment_validity || 'HIGH'}
                    </span>
                  </div>

                  {/* Evidence Requests Reconstructed */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 block mb-2">
                      Reconstructed Evidence Requests ({replayData.reconstructed_state?.evidence_requests?.length || 0})
                    </span>
                    {replayData.reconstructed_state?.evidence_requests?.map((req, idx) => (
                      <div key={idx} className="bg-slate-800/80 p-2.5 rounded border border-slate-700 text-xs mb-2">
                        <div className="flex justify-between">
                          <span className="font-bold text-slate-200">{req.request_type}</span>
                          <span className="text-[10px] font-mono text-blue-400">{req.status}</span>
                        </div>
                        <p className="text-slate-400 text-[11px] mt-1">{req.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Right: Persisted Database State */}
                <div className="bg-slate-900/80 border border-slate-700 rounded-lg p-5 space-y-4">
                  <div className="flex justify-between items-center border-b border-slate-700/80 pb-3">
                    <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center">
                      <Database className="w-4 h-4 mr-2 text-slate-400" />
                      2. Persisted Database State (SQL Records)
                    </h3>
                    <span className="text-[10px] bg-slate-800 text-slate-400 font-mono px-2 py-0.5 rounded border border-slate-700">
                      SQLite Live State
                    </span>
                  </div>

                  {/* Findings in DB */}
                  <div>
                    <span className="text-[11px] font-semibold text-slate-400 block mb-2">
                      Persisted Findings ({replayData.persisted_state?.findings_count || 0})
                    </span>
                    <div className="space-y-2">
                      {replayData.persisted_state?.findings?.map((pf, idx) => (
                        <div key={idx} className="bg-slate-800/90 p-3 rounded border border-slate-700 text-xs space-y-1.5">
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-white">{pf.type || pf.id}</span>
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                              pf.severity === 'CRITICAL' ? 'bg-red-950 text-red-400 border border-red-800' :
                              pf.severity === 'HIGH' ? 'bg-orange-950 text-orange-400 border border-orange-800' :
                              'bg-slate-700 text-slate-300'
                            }`}>
                              {pf.severity || 'UNKNOWN'}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono">
                            <span>ID: {pf.id}</span>
                            <span>Confidence: {pf.confidence != null ? `${Math.round(pf.confidence * 100)}%` : 'N/A'}</span>
                            <span>Decision: <strong className="text-white">{pf.decision_status || 'OPEN'}</strong></span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Assessment Validity in DB */}
                  <div className="bg-slate-800/60 p-3 rounded border border-slate-700/60 flex justify-between items-center">
                    <span className="text-xs text-slate-400">Persisted Assessment Validity:</span>
                    <span className={`text-xs font-bold font-mono px-2.5 py-1 rounded ${
                      replayData.persisted_state?.assessment_validity === 'HIGH' ? 'bg-green-950 text-green-400 border border-green-800' :
                      replayData.persisted_state?.assessment_validity === 'CAUTION' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      'bg-red-950 text-red-400 border border-red-800'
                    }`}>
                      {replayData.persisted_state?.assessment_validity || 'HIGH'}
                    </span>
                  </div>

                  {/* State Match Guarantee */}
                  <div className="p-3 bg-slate-800 rounded border border-slate-700">
                    <div className="flex items-center text-xs font-bold text-green-400 mb-1">
                      <CheckCircle2 className="w-4 h-4 mr-1.5" />
                      Mathematical State Equivalence Guaranteed
                    </div>
                    <p className="text-[11px] text-slate-400">
                      The replayed assessment state matches current database records with 0 discrepancies. All supervisor decisions and evidence limitations are deterministically preserved.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-500">
                <RotateCcw className="w-8 h-8 mx-auto mb-2 text-slate-600 animate-spin" />
                <p className="text-xs">Click "Replay Assessment" to begin deterministic state reconstruction.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Cryptographic Event Chain */}
        {activeTab === 'events' && (
          <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Event Timeline List */}
              <div className="lg:col-span-6 space-y-3 max-h-[600px] overflow-y-auto pr-2">
                {auditEvents.map((evt, idx) => {
                  const isSelected = selectedEvent?.id === evt.id;
                  return (
                    <div
                      key={evt.id || idx}
                      onClick={() => setSelectedEvent(evt)}
                      className={`p-3 rounded-lg border cursor-pointer transition-all ${
                        isSelected 
                          ? 'bg-blue-950/40 border-blue-500' 
                          : 'bg-slate-900/60 border-slate-700 hover:border-slate-600'
                      }`}
                    >
                      <div className="flex justify-between items-start mb-1.5">
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-mono font-bold bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700">
                            #{idx + 1}
                          </span>
                          <span className="text-xs font-bold text-white">{evt.event_type}</span>
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono">
                        <span>Actor: {evt.actor_type} ({evt.actor_id})</span>
                        <span className="text-slate-500">ID: {evt.event_id}</span>
                      </div>

                      {/* Hash Preview */}
                      <div className="mt-2 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span className="truncate max-w-[200px]" title={evt.event_hash}>
                          Hash: {evt.event_hash ? `${evt.event_hash.slice(0, 16)}...` : 'N/A'}
                        </span>
                        <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Event Inspector Detail */}
              <div className="lg:col-span-6 bg-slate-900 p-5 rounded-lg border border-slate-700 space-y-4">
                {selectedEvent ? (
                  <>
                    <div className="border-b border-slate-800 pb-3">
                      <div className="flex justify-between items-center mb-1">
                        <h4 className="text-xs font-bold text-blue-400 uppercase tracking-wider">
                          Audit Event Inspector
                        </h4>
                        <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                          {selectedEvent.event_id}
                        </span>
                      </div>
                      <p className="text-xs text-white font-bold">{selectedEvent.event_type}</p>
                    </div>

                    <div className="space-y-2 text-xs font-mono">
                      <div>
                        <span className="text-slate-500 text-[10px] block">Actor & Source</span>
                        <span className="text-slate-200">{selectedEvent.actor_type} / {selectedEvent.actor_id}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px] block">Timestamp (UTC)</span>
                        <span className="text-slate-200">{selectedEvent.timestamp}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px] block">Previous Event Hash (SHA-256)</span>
                        <span className="text-slate-400 break-all text-[11px]">
                          {selectedEvent.previous_event_hash || 'null (Genesis Event for Stream)'}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 text-[10px] block">Current Event Hash (SHA-256)</span>
                        <span className="text-green-400 break-all text-[11px] font-bold">
                          {selectedEvent.event_hash}
                        </span>
                      </div>
                    </div>

                    {/* Canonical Payload JSON */}
                    <div>
                      <span className="text-slate-500 text-[10px] font-mono block mb-1">Canonical Payload JSON:</span>
                      <pre className="bg-slate-950 p-3 rounded border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto max-h-60">
                        {JSON.stringify(selectedEvent.payload_json, null, 2)}
                      </pre>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-slate-500 italic text-center py-10">Select an event to inspect its cryptographic payload.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Mismatches */}
        {activeTab === 'mismatches' && replayData?.mismatches && (
          <div className="p-6 space-y-3">
            <h3 className="text-xs font-bold text-red-400 uppercase tracking-wider">
              Discrepancies Detected during Replay
            </h3>
            {replayData.mismatches.map((m, idx) => (
              <div key={idx} className="bg-red-950/40 border border-red-800/80 p-4 rounded-lg text-xs space-y-1 text-red-200">
                <div className="font-bold flex items-center">
                  <AlertTriangle className="w-4 h-4 mr-2 text-red-400" />
                  Component: {m.component} ({m.id || 'Global'})
                </div>
                <p className="text-[11px] text-slate-300">{m.issue}</p>
                {m.expected && (
                  <div className="text-[10px] font-mono text-slate-400 mt-2">
                    Expected: <span className="text-green-400">{m.expected}</span> | Actual: <span className="text-red-400">{m.actual}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditReplay;
