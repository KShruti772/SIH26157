import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ArrowLeft, ExternalLink, ShieldAlert, AlertCircle, PlusCircle, CheckCircle2, 
  FileText, Database, Layers, ShieldCheck, AlertTriangle, HelpCircle, Activity,
  Bot, BrainCircuit, Swords, Compass, Send, Check, X, RefreshCw, Sparkles, 
  UserCheck, History, Edit3, XCircle, Clock, Server, ChevronDown, ChevronUp
} from 'lucide-react';
import api from '../services/api';

const FindingDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  // Core Finding & Assurance Data
  const [finding, setFinding] = useState(null);
  const [assurance, setAssurance] = useState(null);
  const [evidenceTrace, setEvidenceTrace] = useState(null);
  const [agentPackage, setAgentPackage] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [evidenceRequests, setEvidenceRequests] = useState([]);

  // UI & Loading States
  const [loading, setLoading] = useState(true);
  const [agentLoading, setAgentLoading] = useState(false);
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [error, setError] = useState(null);
  const [feedbackMsg, setFeedbackMsg] = useState(null);

  // Active Decision Form Mode: 'NONE' | 'CONFIRM' | 'REQUEST_EVIDENCE' | 'MODIFY' | 'REJECT' | 'DEFER'
  const [activeForm, setActiveForm] = useState('NONE');

  // Form Inputs
  const [decisionNotes, setDecisionNotes] = useState('');
  const [decisionRationale, setDecisionRationale] = useState('');
  const [examinerName, setExaminerName] = useState('Supervisory Lead');
  
  // Evidence Request Form Inputs
  const [reqType, setReqType] = useState('CASE_MANAGEMENT_RECORDS');
  const [reqPriority, setReqPriority] = useState('HIGH');
  const [reqReason, setReqReason] = useState('');
  const [reqDesc, setReqDesc] = useState('');

  // Modify Form Inputs
  const [modifiedAssessment, setModifiedAssessment] = useState('');

  // Reject Form Inputs
  const [rejectionReason, setRejectionReason] = useState('EVIDENCE_LIMITATION_INVALIDATES_CONCLUSION');

  // Trace expansion state
  const [traceExpanded, setTraceExpanded] = useState(true);

  useEffect(() => {
    fetchAllData();
  }, [id]);

  const fetchAllData = async () => {
    try {
      // 1. Fetch Finding
      const res = await api.get(`/findings/${id}`);
      setFinding(res.data);
      if (res.data.modified_assessment) {
        setModifiedAssessment(res.data.modified_assessment);
      }

      // 2. Fetch Assessment Assurance Profile
      try {
        const assRes = await api.get(`/assurance/${id}`);
        setAssurance(assRes.data);
      } catch (assErr) {
        console.warn("No specific assurance profile found", assErr);
      }

      // 3. Fetch Operational Evidence Trace
      try {
        const evRes = await api.get(`/evidence/${id}`);
        setEvidenceTrace(evRes.data);
      } catch (evErr) {
        console.warn("Evidence trace not found", evErr);
      }

      // 4. Fetch Latest Agent Review Package
      try {
        const agentRes = await api.get(`/agents/finding/${id}/latest`);
        if (agentRes.data) {
          setAgentPackage(agentRes.data);
        }
      } catch (agentErr) {
        console.warn("No agent review found", agentErr);
      }

      // 5. Fetch Unified Decision & Audit History Timeline
      try {
        const histRes = await api.get(`/findings/${id}/history`);
        setTimeline(histRes.data || []);
      } catch (histErr) {
        console.warn("Could not load history timeline", histErr);
      }

      // 6. Fetch Evidence Requests
      try {
        const reqRes = await api.get(`/findings/${id}/evidence-requests`);
        setEvidenceRequests(reqRes.data || []);
      } catch (reqErr) {
        console.warn("Could not load evidence requests", reqErr);
      }

    } catch (err) {
      console.error("Failed to load finding details", err);
      setError("Finding not found in supervisory database.");
    } finally {
      setLoading(false);
    }
  };

  const handleRunAgentAnalysis = async () => {
    setAgentLoading(true);
    setFeedbackMsg(null);
    try {
      const res = await api.post(`/agents/analyze/${id}`);
      setAgentPackage(res.data);
      setFeedbackMsg("Agent supervisory review completed.");
      // Refresh history
      const histRes = await api.get(`/findings/${id}/history`);
      setTimeline(histRes.data || []);
    } catch (err) {
      console.error("Failed to run agent analysis", err);
      alert("Failed to run agent analysis: " + (err.response?.data?.detail || err.message));
    } finally {
      setAgentLoading(false);
    }
  };

  const handleConfirmDecision = async () => {
    setSubmittingDecision(true);
    setFeedbackMsg(null);
    try {
      await api.post(`/findings/${id}/decision`, {
        decision: 'CONFIRM',
        notes: decisionNotes || "Supervisory finding validated against available evidence.",
        rationale: decisionRationale || finding.rationale,
        reviewer: examinerName,
        agent_run_id: agentPackage?.run_id,
      });
      setFeedbackMsg("Finding successfully confirmed by human examiner.");
      setActiveForm('NONE');
      fetchAllData();
    } catch (err) {
      alert("Error confirming finding: " + (err.response?.data?.detail || err.message));
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleRejectDecision = async () => {
    if (!decisionNotes && !rejectionReason) {
      alert("Please provide a rejection reason or explanatory notes.");
      return;
    }
    setSubmittingDecision(true);
    setFeedbackMsg(null);
    try {
      await api.post(`/findings/${id}/decision`, {
        decision: 'REJECT',
        rejection_reason: rejectionReason,
        notes: decisionNotes || `Rejected based on: ${rejectionReason}`,
        rationale: decisionRationale,
        reviewer: examinerName,
        agent_run_id: agentPackage?.run_id,
      });
      setFeedbackMsg("Finding rejected and recorded in supervisory decision history.");
      setActiveForm('NONE');
      fetchAllData();
    } catch (err) {
      alert("Error rejecting finding: " + (err.response?.data?.detail || err.message));
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleModifyDecision = async () => {
    if (!modifiedAssessment && !decisionNotes) {
      alert("Please provide modified assessment description or notes.");
      return;
    }
    setSubmittingDecision(true);
    setFeedbackMsg(null);
    try {
      await api.post(`/findings/${id}/decision`, {
        decision: 'MODIFY',
        modified_assessment: modifiedAssessment,
        notes: decisionNotes || "Assessment scope modified by examiner.",
        rationale: decisionRationale,
        reviewer: examinerName,
        agent_run_id: agentPackage?.run_id,
      });
      setFeedbackMsg("Supervisory assessment modified and preserved.");
      setActiveForm('NONE');
      fetchAllData();
    } catch (err) {
      alert("Error modifying finding: " + (err.response?.data?.detail || err.message));
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleDeferDecision = async () => {
    setSubmittingDecision(true);
    setFeedbackMsg(null);
    try {
      await api.post(`/findings/${id}/decision`, {
        decision: 'DEFER',
        notes: decisionNotes || "Deferred pending subsequent assessment cycle telemetry.",
        rationale: decisionRationale,
        reviewer: examinerName,
        agent_run_id: agentPackage?.run_id,
      });
      setFeedbackMsg("Finding marked as deferred.");
      setActiveForm('NONE');
      fetchAllData();
    } catch (err) {
      alert("Error deferring finding: " + (err.response?.data?.detail || err.message));
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleCreateEvidenceRequest = async (e) => {
    e.preventDefault();
    if (!reqReason.trim()) {
      alert("Please provide a supervisory justification for the evidence request.");
      return;
    }
    setSubmittingDecision(true);
    setFeedbackMsg(null);
    try {
      await api.post(`/findings/${id}/evidence-requests`, {
        request_type: reqType,
        reason: reqReason,
        description: reqDesc || undefined,
        priority: reqPriority,
        requested_by: examinerName,
      });
      setFeedbackMsg(`Evidence request for ${reqType} created. Finding transitioned to EVIDENCE REQUESTED.`);
      setActiveForm('NONE');
      setReqReason('');
      setReqDesc('');
      fetchAllData();
    } catch (err) {
      alert("Error creating evidence request: " + (err.response?.data?.detail || err.message));
    } finally {
      setSubmittingDecision(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-400">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500 mb-4"></div>
        <p>Loading Human Examiner Workspace & Evidence Trace...</p>
      </div>
    );
  }

  if (error || !finding) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-6 text-red-300">
          <h2 className="text-lg font-bold mb-2 flex items-center">
            <AlertCircle className="w-5 h-5 mr-2" /> Finding Not Found
          </h2>
          <p>{error || "The requested finding ID does not exist."}</p>
          <button 
            onClick={() => navigate('/review-queue')}
            className="mt-4 px-4 py-2 bg-slate-800 text-white rounded hover:bg-slate-700 text-sm"
          >
            Return to Review Queue
          </button>
        </div>
      </div>
    );
  }

  const details = finding.details || {};
  const validityStatus = finding.assessment_validity || assurance?.overall_status || 'HIGH';
  const decisionStatus = finding.decision_status || 'OPEN';
  const limitations = assurance?.limitations || [];
  const blindSpots = assurance?.blind_spots || [];

  const assAgent = agentPackage?.assessment_agent_result;
  const challAgent = agentPackage?.challenge_agent_result;
  const planAgent = agentPackage?.investigation_planner_result;

  return (
    <div className="max-w-7xl mx-auto py-4 space-y-6">
      
      {/* Top Navigation */}
      <div className="flex justify-between items-center">
        <button 
          onClick={() => navigate('/review-queue')}
          className="flex items-center text-slate-400 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4 mr-2" /> Back to Review Queue
        </button>

        <div className="flex items-center space-x-3">
          <span className="text-xs text-slate-400">Examiner Profile:</span>
          <input
            type="text"
            value={examinerName}
            onChange={(e) => setExaminerName(e.target.value)}
            className="bg-slate-800 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-medium focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {feedbackMsg && (
        <div className="bg-emerald-950/40 border border-emerald-700/50 rounded-lg p-3 text-xs text-emerald-300 flex items-center justify-between">
          <span>{feedbackMsg}</span>
          <button onClick={() => setFeedbackMsg(null)} className="text-emerald-400 hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Workspace Card */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 shadow-xl overflow-hidden">
        
        {/* ========================================================================= */}
        {/* SECTION A: FINDING HEADER */}
        {/* ========================================================================= */}
        <div className="bg-slate-900/80 p-6 border-b border-slate-700">
          <div className="flex justify-between items-start mb-4">
            <div>
              <div className="flex items-center space-x-2 mb-1">
                <span className="text-xs uppercase font-bold tracking-wider text-blue-400 block">
                  SUPERVISORY EXAMINER WORKSPACE
                </span>
                <span className="text-slate-500 font-mono text-xs">[{finding.id}]</span>
              </div>
              <h1 className="text-2xl font-bold text-white tracking-wide">{finding.type}</h1>
            </div>

            <div className="flex items-center space-x-2">
              <span className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                finding.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/40' :
                finding.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40' :
                'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40'
              }`}>
                {finding.severity}
              </span>

              {/* Decision State Badge */}
              <span className={`px-3 py-1 rounded text-xs font-bold uppercase ${
                decisionStatus === 'CONFIRMED' ? 'bg-green-500/20 text-green-400 border border-green-500/40' :
                decisionStatus === 'REJECTED' ? 'bg-red-500/20 text-red-400 border border-red-500/40' :
                decisionStatus === 'EVIDENCE_REQUESTED' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' :
                decisionStatus === 'MODIFIED' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40' :
                decisionStatus === 'DEFERRED' ? 'bg-slate-700 text-slate-300' :
                'bg-amber-500/20 text-amber-400 border border-amber-500/40'
              }`}>
                State: {decisionStatus.replace('_', ' ')}
              </span>
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4 text-xs">
            <div>
              <p className="text-slate-500 uppercase font-semibold mb-0.5">Affected Entity</p>
              <Link to={`/entity/${finding.entity_id}`} className="text-blue-400 hover:underline flex items-center font-bold text-sm">
                {finding.entity_id} <ExternalLink className="w-3.5 h-3.5 ml-1" />
              </Link>
            </div>
            <div>
              <p className="text-slate-500 uppercase font-semibold mb-0.5">Category</p>
              <p className="text-slate-200 uppercase font-semibold text-xs mt-0.5">{finding.category?.replace(/_/g, ' ')}</p>
            </div>
            <div>
              <p className="text-slate-500 uppercase font-semibold mb-0.5">Finding Confidence</p>
              <p className="text-white font-bold text-xs mt-0.5">{(finding.confidence * 100).toFixed(0)}% (HIGH)</p>
            </div>
            <div>
              <p className="text-slate-500 uppercase font-semibold mb-0.5">Assessment Validity</p>
              <p className={`font-bold text-xs mt-0.5 uppercase ${
                validityStatus === 'HIGH' ? 'text-green-400' :
                validityStatus === 'CAUTION' ? 'text-amber-400' : 'text-red-400'
              }`}>{validityStatus}</p>
            </div>
            <div>
              <p className="text-slate-500 uppercase font-semibold mb-0.5">Adjudicated By</p>
              <p className="text-slate-300 text-xs mt-0.5">{finding.adjudicated_by || 'Pending Examiner Action'}</p>
            </div>
          </div>

          {/* Supervisory Safety Notice */}
          <div className="bg-blue-950/30 border border-blue-800/40 rounded-lg p-3 text-[11px] text-blue-200 flex items-center justify-between">
            <div className="flex items-center">
              <ShieldCheck className="w-4 h-4 mr-2 text-blue-400 shrink-0" />
              <span>
                <strong>Supervisory Governance Principle:</strong> AI recommendations are advisory. Final supervisory judgement remains with the human examiner.
              </span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Air-Gapped Assessment</span>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* SECTION B & C: WHAT WAS OBSERVED & WHY WAS IT FLAGGED */}
        {/* ========================================================================= */}
        <div className="p-6 border-b border-slate-700 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            
            {/* What Was Observed */}
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/80">
              <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center">
                <Layers className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> B. What Was Observed?
              </h2>
              <div className="bg-slate-800/80 p-3 rounded text-xs text-slate-200 mb-3 leading-relaxed">
                {finding.description}
              </div>
              
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="bg-slate-800 p-2 rounded border border-slate-700">
                  <span className="text-slate-500 block uppercase text-[9px]">Analytic Rule</span>
                  <span className="text-blue-300 font-bold">{finding.analytic_rule || 'HEURISTIC_V1'}</span>
                </div>
                <div className="bg-slate-800 p-2 rounded border border-slate-700">
                  <span className="text-slate-500 block uppercase text-[9px]">Supporting Records</span>
                  <span className="text-white font-bold">{finding.evidence_ids?.length || 0} items</span>
                </div>
              </div>
            </div>

            {/* Why Was This Flagged */}
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/80">
              <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center">
                <HelpCircle className="w-3.5 h-3.5 mr-1.5 text-amber-400" /> C. Why Was This Flagged?
              </h2>
              <div className="bg-slate-800/80 p-3 rounded text-xs text-slate-200 mb-3 leading-relaxed">
                {finding.rationale || "Operational telemetry exhibited execution gaps exceeding normative supervisory thresholds."}
              </div>

              <div className="bg-slate-800 p-2.5 rounded border border-slate-700 text-[11px] text-slate-300">
                <span className="text-slate-400 font-semibold block mb-0.5">Recommended Supervisory Baseline:</span>
                <p className="text-slate-300">{finding.recommended_action}</p>
              </div>
            </div>
          </div>

          {/* Modified Assessment Notice if present */}
          {finding.modified_assessment && (
            <div className="bg-purple-950/25 border border-purple-800/40 rounded-lg p-4 text-xs">
              <h3 className="font-bold text-purple-300 uppercase tracking-wider mb-1 flex items-center">
                <Edit3 className="w-3.5 h-3.5 mr-1.5" /> Human Modified Assessment
              </h3>
              <p className="text-purple-200 leading-relaxed font-sans">{finding.modified_assessment}</p>
              <p className="text-[10px] text-purple-400 mt-1.5">Note: Original machine-generated finding is preserved without modification.</p>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* SECTION D: INTERACTIVE EVIDENCE EXPLORER & TRACE */}
        {/* ========================================================================= */}
        <div className="p-6 border-b border-slate-700 bg-slate-900/30">
          <div className="flex justify-between items-center mb-3">
            <div className="flex items-center space-x-2">
              <Database className="w-4 h-4 text-blue-400" />
              <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                D. Reconstructed Operational Evidence Trace ({evidenceTrace?.alerts?.length || 0} Alerts, {evidenceTrace?.cases?.length || 0} Cases)
              </h2>
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-xs text-slate-400 font-mono">
                Completeness: {((evidenceTrace?.evidence_completeness || 1.0) * 100).toFixed(0)}%
              </span>
              <button
                onClick={() => setTraceExpanded(!traceExpanded)}
                className="text-slate-400 hover:text-white text-xs flex items-center"
              >
                {traceExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Missing Links Callout */}
          {evidenceTrace?.missing_links && evidenceTrace.missing_links.length > 0 && (
            <div className="bg-amber-950/30 border border-amber-800/40 rounded-lg p-3 mb-4 text-xs text-amber-200">
              <span className="font-bold block mb-1 text-amber-300 flex items-center">
                <AlertTriangle className="w-3.5 h-3.5 mr-1" /> Observed Telemetry Visibility Gaps:
              </span>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] font-mono">
                {evidenceTrace.missing_links.map((ml, idx) => (
                  <li key={idx}>{ml}</li>
                ))}
              </ul>
            </div>
          )}

          {traceExpanded && (
            <div className="space-y-4">
              {/* Linked Assets */}
              {evidenceTrace?.assets && evidenceTrace.assets.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  {evidenceTrace.assets.map(ast => (
                    <div key={ast.id} className="bg-slate-800/80 p-2.5 rounded border border-slate-700 text-xs">
                      <div className="flex justify-between font-mono font-bold text-white">
                        <span>{ast.id}</span>
                        <span className={ast.has_telemetry ? 'text-green-400' : 'text-red-400'}>
                          {ast.has_telemetry ? 'Active Telemetry' : 'Missing Telemetry'}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 block mt-0.5">Criticality: {ast.criticality || 'Standard'}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Alert & Timeline Chain */}
              {evidenceTrace?.alerts && evidenceTrace.alerts.length > 0 ? (
                <div className="space-y-3">
                  {evidenceTrace.alerts.slice(0, 5).map(a => (
                    <div key={a.id} className="bg-slate-800 p-3 rounded-lg border border-slate-700 text-xs">
                      <div className="flex justify-between items-center mb-2 border-b border-slate-750 pb-1.5">
                        <span className="font-mono font-bold text-white">{a.id}</span>
                        <span className="text-[11px] text-slate-400">{a.timestamp ? new Date(a.timestamp).toLocaleString() : 'Timestamp unavailable'}</span>
                      </div>
                      <div className="grid grid-cols-4 gap-2 text-[11px] font-mono">
                        <div>
                          <span className="text-slate-500 block">Severity</span>
                          <span className="text-orange-400 font-bold">{a.severity}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Acknowledged</span>
                          <span className={a.acknowledged ? 'text-green-400' : 'text-slate-400'}>{String(a.acknowledged)}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Investigated</span>
                          <span className={a.investigation_started ? 'text-green-400' : 'text-red-400'}>{String(a.investigation_started)}</span>
                        </div>
                        <div>
                          <span className="text-slate-500 block">Escalated</span>
                          <span className={a.escalated ? 'text-green-400' : 'text-red-400'}>{String(a.escalated)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                  {evidenceTrace.alerts.length > 5 && (
                    <p className="text-[11px] text-slate-500 italic text-center">
                      Showing 5 of {evidenceTrace.alerts.length} underlying alert records. Open Evidence Explorer for complete trace.
                    </p>
                  )}
                </div>
              ) : (
                <div className="bg-slate-800 p-4 rounded text-xs text-slate-400 italic text-center">
                  Evidence not directly observable in submitted data (Negative Space finding).
                </div>
              )}
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* SECTION E: ASSESSMENT ASSURANCE */}
        {/* ========================================================================= */}
        {assurance && (
          <div className="p-6 border-b border-slate-700 bg-slate-850">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center">
              <ShieldCheck className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> E. Assessment Assurance & Dimension Profile
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs font-mono mb-4">
              <div className="bg-slate-800 p-3 rounded border border-slate-700">
                <span className="text-slate-500 block text-[10px] uppercase">Overall Validity</span>
                <span className={`font-bold text-sm block mt-0.5 ${
                  validityStatus === 'HIGH' ? 'text-green-400' :
                  validityStatus === 'CAUTION' ? 'text-amber-400' : 'text-red-400'
                }`}>{validityStatus}</span>
              </div>
              <div className="bg-slate-800 p-3 rounded border border-slate-700">
                <span className="text-slate-500 block text-[10px] uppercase">Process Coverage</span>
                <span className="text-amber-400 font-bold text-sm block mt-0.5">
                  {assurance.coverage_details?.process?.status || 'LOW'}
                </span>
              </div>
              <div className="bg-slate-800 p-3 rounded border border-slate-700">
                <span className="text-slate-500 block text-[10px] uppercase">Evidence Dependency</span>
                <span className="text-slate-200 font-bold text-sm block mt-0.5">
                  {assurance.dependency_details?.status?.replace(/_/g, ' ') || 'HIGH INDEPENDENCE'}
                </span>
              </div>
              <div className="bg-slate-800 p-3 rounded border border-slate-700">
                <span className="text-slate-500 block text-[10px] uppercase">Source Integrity</span>
                <span className="text-green-400 font-bold text-sm block mt-0.5">
                  {assurance.integrity_status || 'VERIFIED'}
                </span>
              </div>
            </div>

            <div className="bg-slate-900/50 p-3 rounded border border-slate-700 text-xs text-slate-300">
              <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Supervisory Implication:</span>
              <p className="leading-relaxed">"{assurance.supervisory_interpretation || finding.validity_rationale}"</p>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* SECTION G: AGENTIC SUPERVISORY REVIEW */}
        {/* ========================================================================= */}
        <div className="p-6 border-b border-slate-700 bg-slate-900/90">
          <div className="flex justify-between items-center mb-4">
            <div>
              <div className="flex items-center space-x-2">
                <Bot className="w-5 h-5 text-purple-400" />
                <h2 className="text-xs font-bold text-white uppercase tracking-wider">
                  G. Agentic Supervisory Review (Advisory Reasoning)
                </h2>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Local open-weight model adversarial critique & investigation planning.
              </p>
            </div>

            <button
              onClick={handleRunAgentAnalysis}
              disabled={agentLoading}
              className="flex items-center space-x-1.5 bg-purple-600 hover:bg-purple-700 text-white px-3.5 py-1.5 rounded text-xs font-bold transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1 ${agentLoading ? 'animate-spin' : ''}`} />
              {agentLoading ? 'Analyzing...' : (agentPackage ? 'Re-run Agent Review' : 'Run Agent Review')}
            </button>
          </div>

          {agentPackage ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              
              {/* Assessment Agent */}
              <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex flex-col justify-between text-xs">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-blue-400 uppercase flex items-center">
                      <BrainCircuit className="w-3.5 h-3.5 mr-1" /> 1. Assessment Agent
                    </span>
                    <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded font-bold">
                      Hypothesis
                    </span>
                  </div>
                  <p className="text-slate-200 mb-2 leading-relaxed">{assAgent?.hypothesis}</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Cited Records:</span>
                  <div className="flex flex-wrap gap-1">
                    {assAgent?.supporting_evidence?.slice(0, 4).map(e => (
                      <span key={e} className="px-1.5 py-0.5 bg-slate-900 rounded text-[10px] text-slate-300 font-mono">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Challenge Agent */}
              <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex flex-col justify-between text-xs">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-amber-400 uppercase flex items-center">
                      <Swords className="w-3.5 h-3.5 mr-1" /> 2. Challenge Agent
                    </span>
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-bold uppercase">
                      {challAgent?.challenge_status || 'CRITIQUE'}
                    </span>
                  </div>
                  <p className="text-slate-200 mb-2 italic">"{challAgent?.alternative_explanations?.[0]}"</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Missing Logs:</span>
                  <div className="flex flex-wrap gap-1">
                    {challAgent?.missing_evidence?.map(m => (
                      <span key={m} className="px-1.5 py-0.5 bg-amber-950/40 text-amber-300 rounded text-[10px] font-mono">
                        {m}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Investigation Planner */}
              <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 flex flex-col justify-between text-xs">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-emerald-400 uppercase flex items-center">
                      <Compass className="w-3.5 h-3.5 mr-1" /> 3. Investigation Planner
                    </span>
                    <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-bold">
                      Priority: {planAgent?.priority || 'HIGH'}
                    </span>
                  </div>
                  <p className="text-slate-200 mb-2">{planAgent?.recommended_action}</p>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block mb-1 font-semibold">Next Evidence to Request:</span>
                  {planAgent?.evidence_to_request?.slice(0, 1).map((r, i) => (
                    <span key={i} className="font-mono text-emerald-300 text-[10px] block truncate">
                      {r.type}
                    </span>
                  ))}
                </div>
              </div>

            </div>
          ) : (
            <div className="bg-slate-800/80 p-4 rounded text-center text-slate-400 text-xs">
              No active agent analysis run yet. Trigger agent analysis above to review hypotheses & challenges.
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* SECTION H: HUMAN EXAMINER DECISION WORKSPACE */}
        {/* ========================================================================= */}
        <div className="p-6 border-b border-slate-700 bg-slate-850">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                <UserCheck className="w-4 h-4 mr-2 text-blue-400" /> H. Human Examiner Decision Workspace
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Execute final supervisory action. All decisions are immutably logged with examiner attribution.
              </p>
            </div>
            
            <span className={`px-3 py-1 rounded text-xs font-bold uppercase ${
              decisionStatus === 'CONFIRMED' ? 'bg-green-500/20 text-green-400 border border-green-500/40' :
              decisionStatus === 'REJECTED' ? 'bg-red-500/20 text-red-400 border border-red-500/40' :
              decisionStatus === 'EVIDENCE_REQUESTED' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' :
              'bg-amber-500/20 text-amber-400 border border-amber-500/40'
            }`}>
              Current State: {decisionStatus.replace('_', ' ')}
            </span>
          </div>

          {/* Action Trigger Buttons */}
          <div className="flex flex-wrap gap-2.5 mb-4">
            <button
              onClick={() => setActiveForm('CONFIRM')}
              className={`px-3.5 py-2 rounded text-xs font-bold transition-all ${
                activeForm === 'CONFIRM' ? 'bg-green-600 text-white ring-2 ring-green-400' : 'bg-green-700/80 hover:bg-green-600 text-white'
              }`}
            >
              Confirm Finding
            </button>

            <button
              onClick={() => setActiveForm('REQUEST_EVIDENCE')}
              className={`px-3.5 py-2 rounded text-xs font-bold transition-all ${
                activeForm === 'REQUEST_EVIDENCE' ? 'bg-blue-600 text-white ring-2 ring-blue-400' : 'bg-blue-700/80 hover:bg-blue-600 text-white'
              }`}
            >
              Request Additional Evidence
            </button>

            <button
              onClick={() => setActiveForm('MODIFY')}
              className={`px-3.5 py-2 rounded text-xs font-bold transition-all ${
                activeForm === 'MODIFY' ? 'bg-purple-600 text-white ring-2 ring-purple-400' : 'bg-purple-700/80 hover:bg-purple-600 text-white'
              }`}
            >
              Modify Assessment
            </button>

            <button
              onClick={() => setActiveForm('REJECT')}
              className={`px-3.5 py-2 rounded text-xs font-bold transition-all ${
                activeForm === 'REJECT' ? 'bg-red-600 text-white ring-2 ring-red-400' : 'bg-red-700/80 hover:bg-red-600 text-white'
              }`}
            >
              Reject Finding
            </button>

            <button
              onClick={() => setActiveForm('DEFER')}
              className={`px-3.5 py-2 rounded text-xs font-bold transition-all ${
                activeForm === 'DEFER' ? 'bg-slate-600 text-white ring-2 ring-slate-400' : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
              }`}
            >
              Defer Finding
            </button>
          </div>

          {/* Dynamic Decision Forms */}
          {activeForm === 'CONFIRM' && (
            <div className="bg-slate-900 border border-green-700/50 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold text-green-400 uppercase tracking-wider">Confirm Supervisory Finding</h3>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Supervisory Justification Notes</label>
                <textarea
                  rows="2"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  placeholder="Enter detailed validation rationale confirming this finding..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-green-500"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button onClick={() => setActiveForm('NONE')} className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded text-xs hover:text-white">
                  Cancel
                </button>
                <button 
                  onClick={handleConfirmDecision}
                  disabled={submittingDecision}
                  className="px-4 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded text-xs font-bold transition-colors"
                >
                  {submittingDecision ? 'Submitting...' : 'Submit Confirmation'}
                </button>
              </div>
            </div>
          )}

          {activeForm === 'REQUEST_EVIDENCE' && (
            <form onSubmit={handleCreateEvidenceRequest} className="bg-slate-900 border border-blue-700/50 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold text-blue-400 uppercase tracking-wider">Formulate Supervisory Evidence Request</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Evidence Type Requested</label>
                  <select
                    value={reqType}
                    onChange={(e) => setReqType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-xs text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="CASE_MANAGEMENT_RECORDS">Case Management Records</option>
                    <option value="INVESTIGATION_LOGS">Investigation Records</option>
                    <option value="ESCALATION_RECORDS">Escalation Records</option>
                    <option value="CLOSURE_DISPOSITION_RECORDS">Closure & Disposition Records</option>
                    <option value="ASSET_INVENTORY">Asset Inventory Baseline</option>
                    <option value="TELEMETRY_COVERAGE">Telemetry & Sensor Logs</option>
                    <option value="OTHER">Other Telemetry Export</option>
                  </select>
                </div>
                <div>
                  <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Priority</label>
                  <select
                    value={reqPriority}
                    onChange={(e) => setReqPriority(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-xs text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="HIGH">High Priority</option>
                    <option value="MEDIUM">Medium Priority</option>
                    <option value="LOW">Low Priority</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Supervisory Rationale (Why is this required?)</label>
                <textarea
                  rows="2"
                  value={reqReason}
                  onChange={(e) => setReqReason(e.target.value)}
                  placeholder="Explain why this evidence is necessary to substantiate or resolve the finding..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
                  required
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button type="button" onClick={() => setActiveForm('NONE')} className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded text-xs hover:text-white">
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={submittingDecision}
                  className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-bold transition-colors"
                >
                  {submittingDecision ? 'Submitting...' : 'Dispatch Evidence Request'}
                </button>
              </div>
            </form>
          )}

          {activeForm === 'MODIFY' && (
            <div className="bg-slate-900 border border-purple-700/50 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold text-purple-400 uppercase tracking-wider">Modify Assessment Scope</h3>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Modified Assessment Text</label>
                <textarea
                  rows="2"
                  value={modifiedAssessment}
                  onChange={(e) => setModifiedAssessment(e.target.value)}
                  placeholder="Enter refined human assessment description..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Examiner Notes / Modification Rationale</label>
                <input
                  type="text"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  placeholder="Reason for modifying finding..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button onClick={() => setActiveForm('NONE')} className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded text-xs hover:text-white">
                  Cancel
                </button>
                <button 
                  onClick={handleModifyDecision}
                  disabled={submittingDecision}
                  className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded text-xs font-bold transition-colors"
                >
                  {submittingDecision ? 'Submitting...' : 'Save Modified Assessment'}
                </button>
              </div>
            </div>
          )}

          {activeForm === 'REJECT' && (
            <div className="bg-slate-900 border border-red-700/50 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold text-red-400 uppercase tracking-wider">Reject Supervisory Finding</h3>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Rejection Reason</label>
                <select
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2 text-xs text-white focus:outline-none focus:border-red-500"
                >
                  <option value="EVIDENCE_DISPROVES_FINDING">Evidence disproves finding</option>
                  <option value="NOT_REPRESENTATIVE">Finding is not representative of operational population</option>
                  <option value="EVIDENCE_LIMITATION_INVALIDATES_CONCLUSION">Evidence limitation invalidates conclusion</option>
                  <option value="FALSE_POSITIVE">Verified operational false positive</option>
                  <option value="OTHER">Other justification</option>
                </select>
              </div>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Examiner Explanation Notes</label>
                <textarea
                  rows="2"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  placeholder="Provide detailed explanation for rejecting this finding..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-red-500"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button onClick={() => setActiveForm('NONE')} className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded text-xs hover:text-white">
                  Cancel
                </button>
                <button 
                  onClick={handleRejectDecision}
                  disabled={submittingDecision}
                  className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-bold transition-colors"
                >
                  {submittingDecision ? 'Submitting...' : 'Reject Finding'}
                </button>
              </div>
            </div>
          )}

          {activeForm === 'DEFER' && (
            <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 space-y-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Defer Supervisory Action</h3>
              <div>
                <label className="text-[11px] text-slate-400 uppercase font-semibold block mb-1">Deferral Justification</label>
                <textarea
                  rows="2"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  placeholder="Explain why decision is deferred to a future assessment cycle..."
                  className="w-full bg-slate-800 border border-slate-700 rounded p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-slate-500"
                />
              </div>
              <div className="flex justify-end space-x-2">
                <button onClick={() => setActiveForm('NONE')} className="px-3 py-1.5 bg-slate-800 text-slate-400 rounded text-xs hover:text-white">
                  Cancel
                </button>
                <button 
                  onClick={handleDeferDecision}
                  disabled={submittingDecision}
                  className="px-4 py-1.5 bg-slate-600 hover:bg-slate-500 text-white rounded text-xs font-bold transition-colors"
                >
                  {submittingDecision ? 'Submitting...' : 'Confirm Deferral'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* SECTION I: DECISION HISTORY & AUDIT TRAIL */}
        {/* ========================================================================= */}
        <div className="p-6 bg-slate-900/60">
          <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4 flex items-center">
            <History className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> I. Decision History & Machine-Readable Audit Timeline
          </h2>

          {timeline && timeline.length > 0 ? (
            <div className="relative pl-6 border-l-2 border-slate-700 space-y-4">
              {timeline.map((evt, idx) => (
                <div key={idx} className="relative">
                  <div className="absolute -left-[31px] bg-slate-800 p-1 rounded-full border-2 border-slate-600">
                    <Clock className="w-3.5 h-3.5 text-blue-400" />
                  </div>
                  <div className="bg-slate-800/80 p-3 rounded border border-slate-700/80 text-xs">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-white">{evt.action}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : 'Timestamp'}
                      </span>
                    </div>
                    <p className="text-slate-300 text-[11px] mb-1">{evt.summary}</p>
                    <div className="flex justify-between items-center text-[10px] text-slate-500 font-mono">
                      <span>Actor: {evt.actor}</span>
                      {evt.status && <span>Status: {evt.status}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-500 italic">No previous decisions recorded for this finding.</p>
          )}
        </div>

      </div>
    </div>
  );
};

export default FindingDetail;
