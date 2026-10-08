import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  Activity, AlertTriangle, ShieldAlert, CheckCircle2, Upload, Server, 
  Users, FileBarChart, Eye, Search, Layers, Clock, ArrowRight, ShieldCheck, 
  HelpCircle, RefreshCw, FileText
} from 'lucide-react';
import api from '../services/api';

const StatCard = ({ title, value, subtitle, icon: Icon, color }) => (
  <div className="bg-slate-800 p-5 rounded-lg border border-slate-700 shadow-sm relative overflow-hidden group">
    <div className={`absolute -right-6 -top-6 w-24 h-24 rounded-full opacity-10 transition-transform group-hover:scale-110 ${color}`}></div>
    <div className="flex justify-between items-start relative z-10">
      <div>
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">{title}</p>
        <h3 className="text-2xl font-bold text-white mb-0.5">{value}</h3>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>
      <div className={`p-2.5 rounded-lg bg-slate-700/60 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
    </div>
  </div>
);

const ValidityBadge = ({ validity }) => {
  const v = (validity || 'HIGH').toUpperCase();
  const styles = {
    HIGH: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    CAUTION: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    LOW: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
    INDETERMINATE: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${styles[v] || styles.HIGH}`}>
      {v} VALIDITY
    </span>
  );
};

const CapabilityChip = ({ status }) => {
  const s = (status || 'NOT ASSESSED').toUpperCase();
  if (s === 'OBSERVED CONCERN') {
    return <span className="px-2 py-0.5 rounded text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">OBSERVED CONCERN</span>;
  }
  if (s === 'INSUFFICIENT EVIDENCE') {
    return <span className="px-2 py-0.5 rounded text-xs font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">INSUFFICIENT EVIDENCE</span>;
  }
  if (s === 'NO OBSERVED CONCERN') {
    return <span className="px-2 py-0.5 rounded text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">NO OBSERVED CONCERN</span>;
  }
  return <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-400">NOT ASSESSED</span>;
};

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const res = await api.get('/dashboard/summary');
      setData(res.data);
    } catch (err) {
      console.error("Failed to load supervisory dashboard", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mb-3" />
        <p className="text-sm font-medium">Assembling supervisory dashboard metrics...</p>
      </div>
    );
  }

  const {
    entities_count = 0,
    findings_count = 0,
    high_risk_entities = 0,
    priority_reviews = 0,
    total_uploads = 0,
    total_alerts = 0,
    entities = [],
    supervisory_attention = [],
    findings_by_category = {},
    human_adjudication = {},
    evidence_requests = {},
    capabilities_overview = [],
    assessment_validity_distribution = {},
  } = data || {};

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-800/80 p-6 rounded-xl border border-slate-700 shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">Supervisory Assessment Dashboard</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
              SAT-SA PROTOTYPE
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Deterministic post-operational SOC evaluation for Critical Sector Entities (NTRO / NCIIPC).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchDashboard}
            className="flex items-center bg-slate-700 hover:bg-slate-600 text-slate-200 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors border border-slate-600"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
          <Link
            to="/upload"
            className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-lg shadow-blue-600/20"
          >
            <Upload className="w-4 h-4 mr-2" />
            Ingest CSE Data
          </Link>
        </div>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard 
          title="Assessed Entities" 
          value={entities_count} 
          subtitle={`${total_uploads} total submission(s)`}
          icon={Server} 
          color="text-blue-400 bg-blue-500/20" 
        />
        <StatCard 
          title="Supervisory Findings" 
          value={findings_count} 
          subtitle={`${human_adjudication.confirmed || 0} confirmed, ${human_adjudication.open_under_review || 0} open`}
          icon={Activity} 
          color="text-indigo-400 bg-indigo-500/20" 
        />
        <StatCard 
          title="Supervisory Queue" 
          value={priority_reviews} 
          subtitle="Items requiring examiner triage"
          icon={AlertTriangle} 
          color="text-orange-400 bg-orange-500/20" 
        />
        <StatCard 
          title="Evidence Requests" 
          value={evidence_requests.OPEN || 0} 
          subtitle={`${evidence_requests.TOTAL || 0} total requests issued`}
          icon={Layers} 
          color="text-emerald-400 bg-emerald-500/20" 
        />
      </div>

      {/* Section 1: Entity Overview Cards */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-5">
          <div>
            <h2 className="text-lg font-bold text-white">Critical Sector Entities (CSEs)</h2>
            <p className="text-xs text-slate-400">Assessed entities with telemetry coverage and evidence profiles.</p>
          </div>
          <Link to="/upload" className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center">
            Upload New Submission <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Link>
        </div>

        {entities.length === 0 ? (
          <div className="text-center py-8 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700/50">
            No entities assessed yet. Ingest a dataset submission to begin.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {entities.map(ent => (
              <div key={ent.entity_id} className="bg-slate-900/70 rounded-lg border border-slate-700 p-5 hover:border-slate-600 transition-colors flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="text-base font-bold text-white">{ent.name}</h3>
                      <p className="text-xs text-slate-400">ID: {ent.entity_id} • Sector: {ent.sector}</p>
                    </div>
                    <ValidityBadge validity={ent.assessment_validity} />
                  </div>

                  <div className="grid grid-cols-3 gap-2 my-4 p-3 bg-slate-800/80 rounded border border-slate-700/60 text-center">
                    <div>
                      <span className="text-xs text-slate-400 block">Alerts</span>
                      <span className="text-sm font-bold text-slate-200">{ent.alerts_count}</span>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 block">Cases</span>
                      <span className="text-sm font-bold text-slate-200">{ent.cases_count}</span>
                    </div>
                    <div>
                      <span className="text-xs text-slate-400 block">Assets</span>
                      <span className="text-sm font-bold text-slate-200">{ent.assets_count}</span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-400 mb-4">
                    <span>Findings: <strong className="text-slate-200">{ent.total_findings}</strong></span>
                    <span>Review Pending: <strong className="text-amber-400">{ent.findings_requiring_review}</strong></span>
                    <span>Period: <strong className="text-slate-300">{ent.assessment_period}</strong></span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
                  <Link
                    to={`/entity/${ent.entity_id}`}
                    className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center"
                  >
                    View Entity Assessment <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </Link>
                  <Link
                    to={`/reports`}
                    className="text-xs text-slate-400 hover:text-slate-200 flex items-center"
                  >
                    <FileBarChart className="w-3.5 h-3.5 mr-1" /> Report
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Section 2: Supervisory Attention Grid */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="flex justify-between items-center mb-5">
          <div>
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-bold text-white">Supervisory Attention Feed</h2>
            </div>
            <p className="text-xs text-slate-400">
              High-priority findings requiring human examiner inspection and adjudication.
            </p>
          </div>
          <Link to="/review-queue" className="text-xs font-semibold text-blue-400 hover:text-blue-300 flex items-center">
            Open Full Review Queue <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Link>
        </div>

        {supervisory_attention.length === 0 ? (
          <div className="text-center py-8 text-slate-500 bg-slate-900/50 rounded-lg border border-slate-700/50">
            No priority findings currently flagged for attention.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900 text-xs text-slate-400 uppercase tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-3 px-4 font-semibold">Priority</th>
                  <th className="py-3 px-4 font-semibold">Finding / Type</th>
                  <th className="py-3 px-4 font-semibold">Entity</th>
                  <th className="py-3 px-4 font-semibold">Severity</th>
                  <th className="py-3 px-4 font-semibold">Finding Conf.</th>
                  <th className="py-3 px-4 font-semibold">Assessment Validity</th>
                  <th className="py-3 px-4 font-semibold">Decision State</th>
                  <th className="py-3 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60 bg-slate-800/40">
                {supervisory_attention.map((item, idx) => (
                  <tr key={idx} className="hover:bg-slate-700/40 transition-colors">
                    <td className="py-3.5 px-4 font-bold text-blue-400">
                      {Math.round(item.priority_score || 0)}
                    </td>
                    <td className="py-3.5 px-4">
                      <Link to={`/findings/${item.finding_id}`} className="font-semibold text-white hover:text-blue-400">
                        {item.title}
                      </Link>
                      <p className="text-xs text-slate-400 line-clamp-1 mt-0.5">{item.why_review}</p>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-300">{item.entity_id}</td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        item.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        item.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {item.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-slate-300">
                      {Math.round((item.finding_confidence || 0) * 100)}%
                    </td>
                    <td className="py-3.5 px-4">
                      <ValidityBadge validity={item.assessment_validity} />
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        item.decision_status === 'CONFIRMED' ? 'bg-emerald-500/20 text-emerald-400' :
                        item.decision_status === 'EVIDENCE_REQUESTED' ? 'bg-purple-500/20 text-purple-400' :
                        item.decision_status === 'MODIFIED' ? 'bg-blue-500/20 text-blue-400' :
                        item.decision_status === 'REJECTED' ? 'bg-slate-600 text-slate-400' :
                        'bg-amber-500/20 text-amber-400'
                      }`}>
                        {item.decision_status || 'OPEN'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/findings/${item.finding_id}`}
                        className="inline-flex items-center px-2.5 py-1 bg-blue-600/80 hover:bg-blue-600 text-white rounded text-xs font-semibold transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5 mr-1" /> Examine
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Section 3: 8 Operational Capabilities Overview */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <div className="mb-5">
          <h2 className="text-lg font-bold text-white">8 Operational Capabilities Assessment</h2>
          <p className="text-xs text-slate-400">
            Supervisory evaluation across the 8 NCIIPC capability areas based strictly on observable submission telemetry:
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {capabilities_overview.map((cap, idx) => (
            <div key={idx} className="bg-slate-900/70 p-4 rounded-lg border border-slate-700 flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-sm font-bold text-white">{cap.name}</h3>
                  <span className="text-xs font-mono text-slate-400">#{idx + 1}</span>
                </div>
                <div className="my-2">
                  <CapabilityChip status={cap.status} />
                </div>
                <p className="text-xs text-slate-300 mt-2 line-clamp-2">{cap.observation}</p>
              </div>

              <div className="pt-3 mt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <span>Findings: <strong className="text-slate-200">{cap.findings_count}</strong></span>
                <span className="font-semibold">{cap.assessment_validity} VAL</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Section 4: Dual Insights Grid (Category Breakdown & Human Adjudication) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Finding Categories */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
          <h2 className="text-lg font-bold text-white mb-1">Supervisory Findings Breakdown</h2>
          <p className="text-xs text-slate-400 mb-4">Distribution by analytical rule categorization.</p>

          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-slate-900/60 rounded border border-slate-700/60">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
                <span className="text-sm font-medium text-slate-200">Execution Gaps</span>
              </div>
              <span className="text-sm font-bold text-white">{findings_by_category.execution_gap || 0}</span>
            </div>

            <div className="flex justify-between items-center p-3 bg-slate-900/60 rounded border border-slate-700/60">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
                <span className="text-sm font-medium text-slate-200">Negative Space</span>
              </div>
              <span className="text-sm font-bold text-white">{findings_by_category.negative_space || 0}</span>
            </div>

            <div className="flex justify-between items-center p-3 bg-slate-900/60 rounded border border-slate-700/60">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span className="text-sm font-medium text-slate-200">Statistical Anomalies</span>
              </div>
              <span className="text-sm font-bold text-white">{findings_by_category.anomaly || 0}</span>
            </div>

            <div className="flex justify-between items-center p-3 bg-slate-900/60 rounded border border-slate-700/60">
              <div className="flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                <span className="text-sm font-medium text-slate-200">Peer Deviations</span>
              </div>
              <span className="text-sm font-bold text-white">{findings_by_category.peer_deviation || 0}</span>
            </div>
          </div>
        </div>

        {/* Human Adjudication Status */}
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
          <h2 className="text-lg font-bold text-white mb-1">Human Examiner Adjudication</h2>
          <p className="text-xs text-slate-400 mb-4">Adjudication state of machine and agent findings.</p>

          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="p-3 bg-emerald-500/10 rounded border border-emerald-500/20 text-center">
              <span className="text-xs text-emerald-400 block font-semibold">Confirmed</span>
              <span className="text-xl font-bold text-white">{human_adjudication.confirmed || 0}</span>
            </div>
            <div className="p-3 bg-purple-500/10 rounded border border-purple-500/20 text-center">
              <span className="text-xs text-purple-400 block font-semibold">Evidence Requested</span>
              <span className="text-xl font-bold text-white">{human_adjudication.evidence_requested || 0}</span>
            </div>
            <div className="p-3 bg-blue-500/10 rounded border border-blue-500/20 text-center">
              <span className="text-xs text-blue-400 block font-semibold">Modified</span>
              <span className="text-xl font-bold text-white">{human_adjudication.modified || 0}</span>
            </div>
            <div className="p-3 bg-slate-700/40 rounded border border-slate-600 text-center">
              <span className="text-xs text-slate-400 block font-semibold">Rejected / Adjudicated</span>
              <span className="text-xl font-bold text-white">{human_adjudication.rejected || 0}</span>
            </div>
          </div>

          <div className="p-3 bg-slate-900/60 rounded border border-slate-700 flex items-center justify-between text-xs text-slate-400">
            <span>Open for Examination: <strong className="text-amber-400">{human_adjudication.open_under_review || 0}</strong></span>
            <span>Total Evaluated: <strong className="text-slate-200">{human_adjudication.total_findings || 0}</strong></span>
          </div>
        </div>
      </div>

      {/* Section 5: Fast Navigation Actions */}
      <div className="bg-slate-800/60 rounded-xl border border-slate-700 p-6 shadow-sm">
        <h2 className="text-base font-bold text-white mb-4">Supervisory Navigation & Reporting</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <Link
            to="/review-queue"
            className="p-4 bg-slate-800 hover:bg-slate-700/80 rounded-lg border border-slate-700 transition-colors flex items-center gap-3"
          >
            <div className="p-2.5 rounded bg-blue-500/20 text-blue-400">
              <Eye className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block">Review Queue</span>
              <span className="text-xs text-slate-400">Examiner triage feed</span>
            </div>
          </Link>

          <Link
            to="/findings"
            className="p-4 bg-slate-800 hover:bg-slate-700/80 rounded-lg border border-slate-700 transition-colors flex items-center gap-3"
          >
            <div className="p-2.5 rounded bg-indigo-500/20 text-indigo-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block">Supervisory Findings</span>
              <span className="text-xs text-slate-400">All analytic findings</span>
            </div>
          </Link>

          <Link
            to="/benchmarks"
            className="p-4 bg-slate-800 hover:bg-slate-700/80 rounded-lg border border-slate-700 transition-colors flex items-center gap-3"
          >
            <div className="p-2.5 rounded bg-purple-500/20 text-purple-400">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block">Peer Benchmarks</span>
              <span className="text-xs text-slate-400">Cohort percentile metrics</span>
            </div>
          </Link>

          <Link
            to="/reports"
            className="p-4 bg-slate-800 hover:bg-slate-700/80 rounded-lg border border-slate-700 transition-colors flex items-center gap-3"
          >
            <div className="p-2.5 rounded bg-emerald-500/20 text-emerald-400">
              <FileBarChart className="w-5 h-5" />
            </div>
            <div>
              <span className="text-sm font-bold text-white block">Report Generation</span>
              <span className="text-xs text-slate-400">Export JSON & PDF</span>
            </div>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
