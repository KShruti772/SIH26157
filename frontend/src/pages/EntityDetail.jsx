import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  Building2, ShieldAlert, Activity, ArrowLeft, Download, FileText, 
  Layers, CheckCircle2, Clock, Eye, AlertTriangle, RefreshCw, FileBarChart 
} from 'lucide-react';
import api from '../services/api';

const ValidityBadge = ({ validity }) => {
  const v = (validity || 'HIGH').toUpperCase();
  const styles = {
    HIGH: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    CAUTION: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    LOW: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    INDETERMINATE: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  };
  return (
    <span className={`px-2.5 py-1 rounded text-xs font-bold border ${styles[v] || styles.HIGH}`}>
      {v} VALIDITY
    </span>
  );
};

const CapabilityChip = ({ status }) => {
  const s = (status || 'NOT ASSESSED').toUpperCase();
  if (s === 'OBSERVED CONCERN') {
    return <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">OBSERVED CONCERN</span>;
  }
  if (s === 'INSUFFICIENT EVIDENCE') {
    return <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">INSUFFICIENT EVIDENCE</span>;
  }
  if (s === 'NO OBSERVED CONCERN') {
    return <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">NO OBSERVED CONCERN</span>;
  }
  return <span className="px-2.5 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-400">NOT ASSESSED</span>;
};

const EntityDetail = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const fetchEntityAssessment = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/entities/${id}/assessment`);
        setData(res.data);
      } catch (err) {
        console.error("Failed to load entity assessment", err);
      } finally {
        setLoading(false);
      }
    };
    fetchEntityAssessment();
  }, [id]);

  const handleDownloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await api.get(`/reports/${id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SAT_SA_Assessment_${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Failed to download PDF", err);
      alert("Failed to export PDF report. Please ensure backend is running.");
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadJson = async () => {
    try {
      const res = await api.get(`/reports/${id}/json`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SAT_SA_Report_${id}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Failed to download JSON", err);
      alert("Failed to export JSON report.");
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mb-3" />
        <p className="text-sm font-medium">Assembling entity supervisory assessment for {id}...</p>
      </div>
    );
  }

  if (!data || !data.entity) {
    return (
      <div className="max-w-4xl mx-auto py-12 text-center">
        <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Entity Not Found</h2>
        <p className="text-slate-400 mb-6">No assessment records found for entity '{id}'.</p>
        <Link to="/" className="px-4 py-2 bg-slate-700 text-white rounded font-medium hover:bg-slate-600 transition-colors">
          Return to Dashboard
        </Link>
      </div>
    );
  }

  const {
    entity,
    assessment_id,
    source_submission,
    record_counts = {},
    supervisory_attention = [],
    capabilities = [],
    findings_summary = {},
    assurance,
    evidence_limitations = {},
    human_adjudication = {},
    evidence_requests = [],
  } = data;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Back Link & Header */}
      <div>
        <Link to="/" className="text-xs text-slate-400 hover:text-slate-200 flex items-center mb-3">
          <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Back to Supervisory Dashboard
        </Link>
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-blue-900/50 rounded-xl border border-blue-500/40 flex items-center justify-center shrink-0">
              <Building2 className="w-7 h-7 text-blue-400" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-white">{entity.name}</h1>
                <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-slate-700 text-slate-300">
                  {entity.id}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Sector: <strong className="text-slate-200">{entity.sector}</strong> • Assessment Period: <strong className="text-slate-200">{entity.assessment_period || 'Not provided'}</strong>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadJson}
              className="flex items-center px-3.5 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-xs font-semibold transition-colors border border-slate-600"
            >
              <Download className="w-4 h-4 mr-1.5" /> Export JSON
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={downloading}
              className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white rounded-lg text-xs font-bold transition-colors shadow-lg shadow-blue-600/20"
            >
              <FileText className="w-4 h-4 mr-1.5" /> {downloading ? 'Generating PDF...' : 'Download Assessment PDF'}
            </button>
          </div>
        </div>
      </div>

      {/* Submission & Scope Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 text-center">
          <span className="text-xs text-slate-400 uppercase font-semibold block mb-1">Observable Alerts</span>
          <span className="text-2xl font-bold text-white">{record_counts.alerts || 0}</span>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 text-center">
          <span className="text-xs text-slate-400 uppercase font-semibold block mb-1">Case Records</span>
          <span className="text-2xl font-bold text-white">{record_counts.cases || 0}</span>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 text-center">
          <span className="text-xs text-slate-400 uppercase font-semibold block mb-1">Infrastructure Assets</span>
          <span className="text-2xl font-bold text-white">{record_counts.assets || 0}</span>
        </div>
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700 text-center">
          <span className="text-xs text-slate-400 uppercase font-semibold block mb-1">Assessment Validity</span>
          <div className="mt-1">
            <ValidityBadge validity={assurance?.assessment_validity || 'HIGH'} />
          </div>
        </div>
      </div>

      {/* 8 Capabilities View */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="mb-5">
          <h2 className="text-lg font-bold text-white">8 Operational Capabilities Assessment</h2>
          <p className="text-xs text-slate-400">
            Evidence-grounded evaluation across the 8 NCIIPC capability dimensions. Absence of finding is not equivalent to proof of health.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {capabilities.map((cap, idx) => (
            <div key={idx} className="bg-slate-900/80 p-4 rounded-lg border border-slate-700/80 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-sm font-bold text-white">{cap.name}</h3>
                  <span className="text-xs font-mono text-slate-500">#{idx + 1}</span>
                </div>
                <div className="my-2">
                  <CapabilityChip status={cap.status} />
                </div>
                <p className="text-xs text-slate-300 mt-2">{cap.observation}</p>
                {cap.implication && (
                  <p className="text-xs text-slate-400 italic mt-1 border-l-2 border-slate-700 pl-2">
                    {cap.implication}
                  </p>
                )}
              </div>

              <div className="pt-3 mt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>Findings: <strong className="text-slate-200">{cap.findings_count}</strong></span>
                <span className="font-semibold text-slate-300">{cap.assessment_validity} VAL</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Supervisory Findings for this Entity */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-5">
          <div>
            <h2 className="text-lg font-bold text-white">Entity Supervisory Findings</h2>
            <p className="text-xs text-slate-400">Flagged execution gaps, negative space, and anomalies for {entity.name}.</p>
          </div>
          <Link to="/findings" className="text-xs text-blue-400 hover:text-blue-300 flex items-center">
            View All Findings <ArrowLeft className="w-3.5 h-3.5 ml-1 rotate-180" />
          </Link>
        </div>

        {supervisory_attention.length === 0 ? (
          <div className="text-center py-8 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700/50">
            No supervisory findings recorded for this entity.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-3 px-4 font-semibold">Priority</th>
                  <th className="py-3 px-4 font-semibold">Finding / Type</th>
                  <th className="py-3 px-4 font-semibold">Category</th>
                  <th className="py-3 px-4 font-semibold">Severity</th>
                  <th className="py-3 px-4 font-semibold">Finding Conf.</th>
                  <th className="py-3 px-4 font-semibold">Assessment Validity</th>
                  <th className="py-3 px-4 font-semibold">Decision</th>
                  <th className="py-3 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60 bg-slate-800/40">
                {supervisory_attention.map((f, idx) => (
                  <tr key={idx} className="hover:bg-slate-700/40 transition-colors">
                    <td className="py-3.5 px-4 font-bold text-blue-400">{Math.round(f.priority_score || 0)}</td>
                    <td className="py-3.5 px-4">
                      <Link to={`/findings/${f.finding_id}`} className="font-semibold text-white hover:text-blue-400">
                        {f.title}
                      </Link>
                      <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">{f.description}</p>
                    </td>
                    <td className="py-3.5 px-4 text-xs font-mono text-slate-400">{f.category}</td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        f.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        f.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {f.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-300">
                      {Math.round((f.finding_confidence || 0) * 100)}%
                    </td>
                    <td className="py-3.5 px-4">
                      <ValidityBadge validity={f.assessment_validity} />
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-700 text-slate-300">
                        {f.decision_status || 'OPEN'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/findings/${f.finding_id}`}
                        className="inline-flex items-center px-2.5 py-1 bg-blue-600/80 hover:bg-blue-600 text-white rounded text-xs font-semibold transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" /> Workspace
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Assurance Matrix & Limitations Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Assurance Matrix */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold text-white">Assessment Assurance Profile</h2>
            <ValidityBadge validity={assurance?.assessment_validity || 'HIGH'} />
          </div>
          <p className="text-xs text-slate-400 mb-4">{assurance?.validity_rationale}</p>

          <div className="space-y-2.5">
            {assurance?.dimension_details && Object.entries(assurance.dimension_details).map(([k, v]) => (
              <div key={k} className="p-3 bg-slate-900/60 rounded border border-slate-700/60 flex justify-between items-start text-xs">
                <div>
                  <span className="font-bold text-white uppercase tracking-wider block mb-0.5">
                    {k.replace('_', ' ')}
                  </span>
                  <p className="text-slate-300">{v.observation || 'No gaps detected.'}</p>
                </div>
                <span className={`px-2 py-0.5 rounded font-bold uppercase ml-3 shrink-0 ${
                  v.status === 'LOW' ? 'bg-red-500/20 text-red-400' :
                  v.status === 'CAUTION' || v.status === 'PARTIAL' ? 'bg-amber-500/20 text-amber-400' :
                  'bg-emerald-500/20 text-emerald-400'
                }`}>
                  {v.status || 'HIGH'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Evidence Limitations */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
          <h2 className="text-lg font-bold text-white mb-1">Evidence Limitations</h2>
          <p className="text-xs text-slate-400 mb-4">Segregated breakdown of missing, partial, unknown, and contradictory evidence.</p>

          <div className="space-y-3">
            {evidence_limitations.missing?.length > 0 && (
              <div className="p-3 bg-rose-500/10 rounded border border-rose-500/20">
                <span className="text-xs font-bold text-rose-400 uppercase block mb-1">Missing Evidence</span>
                {evidence_limitations.missing.map((m, i) => (
                  <p key={i} className="text-xs text-slate-300 mb-1">• <strong>{m.item}:</strong> {m.observation}</p>
                ))}
              </div>
            )}

            {evidence_limitations.partial?.length > 0 && (
              <div className="p-3 bg-amber-500/10 rounded border border-amber-500/20">
                <span className="text-xs font-bold text-amber-400 uppercase block mb-1">Partial Process Coverage</span>
                {evidence_limitations.partial.map((p, i) => (
                  <p key={i} className="text-xs text-slate-300 mb-1">• <strong>{p.item}:</strong> {p.observation}</p>
                ))}
              </div>
            )}

            {evidence_limitations.unknown?.length > 0 && (
              <div className="p-3 bg-slate-900/60 rounded border border-slate-700">
                <span className="text-xs font-bold text-slate-400 uppercase block mb-1">Unknown Denominators</span>
                {evidence_limitations.unknown.map((u, i) => (
                  <p key={i} className="text-xs text-slate-300 mb-1">• <strong>{u.item}:</strong> {u.observation}</p>
                ))}
              </div>
            )}

            {(!evidence_limitations.missing || evidence_limitations.missing.length === 0) &&
             (!evidence_limitations.partial || evidence_limitations.partial.length === 0) && (
              <div className="p-4 bg-emerald-500/10 rounded border border-emerald-500/20 text-xs text-emerald-400">
                No critical evidence limitations flagged in submitted data.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Outstanding Evidence Requests Table */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-lg font-bold text-white">Active Evidence Requests</h2>
            <p className="text-xs text-slate-400">Formal requests issued to CSE by supervisory examiners.</p>
          </div>
        </div>

        {evidence_requests.length === 0 ? (
          <div className="text-center py-6 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700/50 text-xs">
            No evidence requests currently active for {entity.name}.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">Request ID</th>
                  <th className="py-2.5 px-3 font-semibold">Type</th>
                  <th className="py-2.5 px-3 font-semibold">Priority</th>
                  <th className="py-2.5 px-3 font-semibold">Status</th>
                  <th className="py-2.5 px-3 font-semibold">Reason</th>
                  <th className="py-2.5 px-3 font-semibold">Requested By</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60 bg-slate-800/40">
                {evidence_requests.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-700/40 transition-colors text-xs">
                    <td className="py-2.5 px-3 font-mono font-bold text-blue-400">{r.id}</td>
                    <td className="py-2.5 px-3 font-semibold text-white">{r.request_type}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded font-bold bg-amber-500/20 text-amber-400">
                        {r.priority || 'HIGH'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded font-bold ${
                        r.status === 'OPEN' ? 'bg-purple-500/20 text-purple-400' : 'bg-emerald-500/20 text-emerald-400'
                      }`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 max-w-xs truncate">{r.reason}</td>
                    <td className="py-2.5 px-3 text-slate-400">{r.requested_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default EntityDetail;
