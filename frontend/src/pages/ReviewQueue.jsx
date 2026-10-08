import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Eye, UserPlus, CheckSquare, XSquare, ExternalLink, Filter, 
  ArrowUpDown, ShieldAlert, Bot, HelpCircle, Layers, CheckCircle2,
  AlertTriangle, Clock, Search
} from 'lucide-react';
import api from '../services/api';

const ReviewQueue = () => {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filter States
  const [entityFilter, setEntityFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [validityFilter, setValidityFilter] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('');
  const [agentFilter, setAgentFilter] = useState('');
  const [sortBy, setSortBy] = useState('priority');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchQueue();
  }, [entityFilter, severityFilter, categoryFilter, validityFilter, decisionFilter, agentFilter, sortBy, sortOrder]);

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const params = {};
      if (entityFilter) params.entity_id = entityFilter;
      if (severityFilter) params.severity = severityFilter;
      if (categoryFilter) params.category = categoryFilter;
      if (validityFilter) params.validity = validityFilter;
      if (decisionFilter) params.decision_status = decisionFilter;
      if (agentFilter) params.agent_status = agentFilter;
      params.sort_by = sortBy;
      params.order = sortOrder;

      const res = await api.get('/review-queue', { params });
      setQueue(res.data);
    } catch (err) {
      console.error("Failed to fetch review queue:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (id, status) => {
    try {
      await api.patch(`/review-queue/${id}`, { status });
      fetchQueue();
    } catch (err) {
      console.error(err);
    }
  };

  const handleAssign = async (id) => {
    const reviewer = prompt("Enter examiner / reviewer name:");
    if (reviewer) {
      try {
        await api.patch(`/review-queue/${id}`, { status: 'Assigned', reviewer });
        fetchQueue();
      } catch (err) {
        console.error(err);
      }
    }
  };

  const resetFilters = () => {
    setEntityFilter('');
    setSeverityFilter('');
    setCategoryFilter('');
    setValidityFilter('');
    setDecisionFilter('');
    setAgentFilter('');
    setSortBy('priority');
    setSortOrder('desc');
  };

  return (
    <div className="max-w-7xl mx-auto flex flex-col h-full py-4">
      {/* Page Header */}
      <div className="mb-5 shrink-0 flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Human Examiner Priority Queue</h1>
          <p className="text-slate-400 text-sm">
            Triage, inspect evidence, review agent reasoning, and record formal supervisory decisions.
          </p>
        </div>
        <div className="bg-slate-800/80 border border-slate-700 px-4 py-2 rounded-lg text-right">
          <span className="text-[11px] text-slate-400 block uppercase">Total Findings in Queue</span>
          <span className="text-xl font-bold text-blue-400 font-mono">{queue.length}</span>
        </div>
      </div>

      {/* Filter & Sort Bar */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 mb-5 shadow-sm">
        <div className="flex items-center justify-between mb-3 border-b border-slate-700/60 pb-2">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center">
            <Filter className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> Queue Filters & Sorting
          </span>
          <button
            onClick={resetFilters}
            className="text-xs text-slate-400 hover:text-white transition-colors underline"
          >
            Reset Filters
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 text-xs">
          {/* Entity Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Entity / CSE</label>
            <input
              type="text"
              placeholder="e.g. CSE-001"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Severity Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Severity</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Categories</option>
              <option value="execution_gap">Execution Gap</option>
              <option value="negative_space">Negative Space</option>
              <option value="anomaly">Anomaly</option>
              <option value="peer_deviation">Peer Deviation</option>
            </select>
          </div>

          {/* Validity Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Assessment Validity</label>
            <select
              value={validityFilter}
              onChange={(e) => setValidityFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Validities</option>
              <option value="HIGH">High</option>
              <option value="CAUTION">Caution</option>
              <option value="LOW">Low</option>
              <option value="INDETERMINATE">Indeterminate</option>
            </select>
          </div>

          {/* Decision Status Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Decision State</label>
            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All States</option>
              <option value="OPEN">Open</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="EVIDENCE_REQUESTED">Evidence Requested</option>
              <option value="MODIFIED">Modified</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="REJECTED">Rejected</option>
              <option value="DEFERRED">Deferred</option>
            </select>
          </div>

          {/* Agent Status Filter */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Agent Review</label>
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
            >
              <option value="">All Agent States</option>
              <option value="NOT_STARTED">Not Started</option>
              <option value="REQUIRED">Review Required</option>
              <option value="COMPLETED">Completed</option>
            </select>
          </div>

          {/* Sort By */}
          <div>
            <label className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">Sort By</label>
            <div className="flex space-x-1">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value="priority">Priority</option>
                <option value="severity">Severity</option>
                <option value="confidence">Confidence</option>
                <option value="validity">Validity</option>
                <option value="created_at">Date</option>
              </select>
              <button
                onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
                title={`Sort Order: ${sortOrder.toUpperCase()}`}
                className="bg-slate-900 border border-slate-700 px-2 rounded text-slate-300 hover:text-white"
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Queue List Container */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden flex flex-col shadow-xl">
        <div className="flex-1 overflow-auto p-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-48 text-slate-400">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-3"></div>
              <p className="text-xs">Loading filtered supervisory queue...</p>
            </div>
          ) : queue.length === 0 ? (
            <div className="bg-slate-900/60 border border-slate-700/60 rounded-lg p-10 text-center text-slate-400">
              <ShieldAlert className="w-8 h-8 text-slate-500 mx-auto mb-2" />
              <p className="font-semibold text-sm text-slate-300 mb-1">No findings matching current criteria</p>
              <p className="text-xs text-slate-500 mb-4">Try clearing filters to view all pending supervisory items.</p>
              <button
                onClick={resetFilters}
                className="px-3 py-1.5 bg-slate-800 border border-slate-600 rounded text-xs text-white hover:bg-slate-700"
              >
                Reset All Filters
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {queue.map((item, index) => {
                const f = item.finding;
                const r = item.review_item;
                const validity = f.assessment_validity || 'HIGH';
                const decision = f.decision_status || 'OPEN';

                return (
                  <div key={r.id} className="bg-slate-900 border border-slate-700 rounded-lg p-5 relative overflow-hidden transition-all hover:border-slate-600 shadow-sm">
                    {/* Severity indicator strip */}
                    <div className={`absolute left-0 top-0 bottom-0 w-1.5 ${
                      f.severity === 'CRITICAL' ? 'bg-red-500' :
                      f.severity === 'HIGH' ? 'bg-orange-500' :
                      f.severity === 'MEDIUM' ? 'bg-yellow-500' : 'bg-blue-500'
                    }`}></div>
                    
                    <div className="flex justify-between items-start mb-3 pl-3">
                      <div>
                        <div className="flex items-center space-x-2 mb-1.5">
                          <span className="text-xs font-bold text-slate-400">#{index + 1}</span>
                          <Link to={`/entity/${f.entity_id}`} className="text-xs bg-slate-800 text-blue-400 px-2 py-0.5 rounded border border-slate-700 hover:underline font-bold">
                            {f.entity_id}
                          </Link>
                          <span className="text-xs text-slate-500 font-mono">[{f.id}]</span>
                          
                          {/* Decision Badge */}
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            decision === 'CONFIRMED' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                            decision === 'REJECTED' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                            decision === 'EVIDENCE_REQUESTED' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                            decision === 'MODIFIED' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                            decision === 'DEFERRED' ? 'bg-slate-700 text-slate-300' :
                            'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          }`}>
                            {decision.replace('_', ' ')}
                          </span>

                          {/* Agent status */}
                          {item.agent_review_status && item.agent_review_status !== 'NOT_STARTED' && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center">
                              <Bot className="w-3 h-3 mr-1" /> Agent Review: {item.agent_review_status}
                            </span>
                          )}
                        </div>

                        <h3 className="text-base font-bold text-white tracking-wide">{f.type}</h3>
                      </div>
                      
                      <div className="text-right">
                        <p className="text-[10px] text-slate-400 uppercase font-semibold mb-0.5">Priority Score</p>
                        <div className="text-xl font-bold text-white">
                          {r.priority_score.toFixed(0)}<span className="text-xs text-slate-500 font-normal">/100</span>
                        </div>
                      </div>
                    </div>

                    {/* Why Review Callout */}
                    <div className="bg-slate-800/80 border border-slate-700/80 rounded p-2.5 mb-3 pl-3 text-xs text-slate-300">
                      <span className="text-[10px] uppercase font-bold text-slate-400 block mb-0.5">Supervisory Context:</span>
                      <p>{item.why_review || f.description}</p>
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4 pl-3 text-xs">
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold">Severity</p>
                        <p className={`text-xs font-bold mt-0.5 ${
                          f.severity === 'CRITICAL' ? 'text-red-400' :
                          f.severity === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                        }`}>{f.severity}</p>
                      </div>

                      <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold">Finding Confidence</p>
                        <p className="text-xs text-white font-medium mt-0.5">{(f.confidence * 100).toFixed(0)}% (HIGH)</p>
                      </div>

                      <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold">Assessment Validity</p>
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold mt-0.5 uppercase ${
                          validity === 'HIGH' ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
                          validity === 'CAUTION' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                          validity === 'LOW' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                          'bg-slate-700 text-slate-300'
                        }`}>
                          {validity}
                        </span>
                      </div>

                      <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold">Evidence Completeness</p>
                        <p className="text-xs text-slate-200 font-mono mt-0.5">
                          {((item.evidence_completeness || 1.0) * 100).toFixed(0)}%
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] text-slate-500 uppercase font-semibold">Review Assignment</p>
                        <p className="text-xs text-blue-400 font-medium mt-0.5">{r.status}</p>
                        {r.reviewer && <p className="text-[10px] text-slate-400">({r.reviewer})</p>}
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap gap-2 pt-3 border-t border-slate-800 pl-3">
                      <Link 
                        to={`/findings/${f.id}`}
                        className="flex items-center text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 px-3.5 py-1.5 rounded transition-colors shadow-sm"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1.5" /> Open Examiner Workspace
                      </Link>
                      <Link 
                        to={`/evidence/${f.id}`}
                        className="flex items-center text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded border border-slate-700 transition-colors"
                      >
                        <ExternalLink className="w-3.5 h-3.5 mr-1.5" /> View Evidence Trace
                      </Link>
                      <button 
                        onClick={() => handleAssign(r.id)}
                        className="flex items-center text-xs font-medium text-blue-300 bg-blue-900/30 hover:bg-blue-900/50 px-3 py-1.5 rounded border border-blue-800 transition-colors"
                      >
                        <UserPlus className="w-3.5 h-3.5 mr-1.5" /> Assign Examiner
                      </button>

                      <div className="flex-1"></div>

                      <button 
                        onClick={() => handleUpdateStatus(r.id, 'Reviewed')}
                        className="flex items-center text-xs font-medium text-green-400 bg-green-900/20 hover:bg-green-900/40 px-3 py-1.5 rounded border border-green-800 transition-colors"
                      >
                        <CheckSquare className="w-3.5 h-3.5 mr-1.5" /> Mark Triage Complete
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReviewQueue;
