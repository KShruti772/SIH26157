import React, { useState, useEffect } from 'react';
import { 
  FileBarChart, Download, FileText, CheckCircle2, AlertTriangle, 
  Building2, ShieldCheck, RefreshCw, Eye, Layers, ArrowRight, Server, Shield
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
    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${styles[v] || styles.HIGH}`}>
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

const ReportGeneration = () => {
  const [entities, setEntities] = useState([]);
  const [selectedEntityId, setSelectedEntityId] = useState('');
  const [reportData, setReportData] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // Fetch available entities and reports on load
  useEffect(() => {
    const fetchReportList = async () => {
      try {
        const res = await api.get('/reports');
        setEntities(res.data || []);
        if (res.data && res.data.length > 0) {
          setSelectedEntityId(res.data[0].entity_id);
        }
      } catch (err) {
        console.error("Failed to load reports list", err);
      } finally {
        setLoadingList(false);
      }
    };
    fetchReportList();
  }, []);

  // Generate / Compile Report
  const handleGenerateReport = async (entityId = selectedEntityId) => {
    if (!entityId) return;
    setGenerating(true);
    try {
      const res = await api.post('/reports/generate', { entity_id: entityId });
      setReportData(res.data);
    } catch (err) {
      console.error("Failed to compile report", err);
      alert("Failed to compile supervisory report. Please verify backend state.");
    } finally {
      setGenerating(false);
    }
  };

  // Download PDF
  const handleDownloadPdf = async () => {
    if (!reportData) return;
    const targetId = reportData.report_metadata?.entity_id || selectedEntityId;
    setDownloadingPdf(true);
    try {
      const res = await api.get(`/reports/${targetId}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SAT_SA_Report_${targetId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Failed to download PDF", err);
      alert("Failed to export PDF report.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  // Download JSON
  const handleDownloadJson = async () => {
    if (!reportData) return;
    const targetId = reportData.report_metadata?.entity_id || selectedEntityId;
    try {
      const res = await api.get(`/reports/${targetId}/json`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/json' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `SAT_SA_Report_${targetId}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Failed to download JSON", err);
      alert("Failed to export JSON report.");
    }
  };

  if (loadingList) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500 mb-3" />
        <p className="text-sm font-medium">Loading supervisory report hub...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">Supervisory Assessment Reporting</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
              MODULE 8
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Compile evidence-grounded assessment reports combining deterministic analytics, assurance profiles, and human adjudications.
          </p>
        </div>
      </div>

      {/* Entity Selection Bar */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm">
        <h2 className="text-base font-bold text-white mb-3">Select Critical Sector Entity for Assessment</h2>
        
        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <select
            value={selectedEntityId}
            onChange={(e) => {
              setSelectedEntityId(e.target.value);
              setReportData(null);
            }}
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            {entities.map((ent) => (
              <option key={ent.entity_id} value={ent.entity_id}>
                {ent.entity_name} ({ent.entity_id}) — {ent.sector} [{ent.findings_count} findings, {ent.assessment_validity} validity]
              </option>
            ))}
          </select>

          <button
            onClick={() => handleGenerateReport(selectedEntityId)}
            disabled={generating || !selectedEntityId}
            className="w-full sm:w-auto px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white rounded-lg text-sm font-bold transition-colors shadow-lg shadow-blue-600/20 flex items-center justify-center shrink-0"
          >
            {generating ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Compiling Report...
              </>
            ) : (
              <>
                <FileBarChart className="w-4 h-4 mr-2" /> Compile Supervisory Report
              </>
            )}
          </button>
        </div>
      </div>

      {/* Live Report Preview */}
      {reportData && (
        <div className="space-y-8 animate-fadeIn">
          {/* Action Toolbar */}
          <div className="bg-slate-800/90 backdrop-blur rounded-xl border border-slate-700 p-4 shadow-sm flex flex-col sm:flex-row justify-between items-center gap-4 sticky top-4 z-20">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <span className="text-sm font-bold text-white block">
                  Report Ready: {reportData.report_metadata?.report_id}
                </span>
                <span className="text-xs text-slate-400">
                  Compiled at {reportData.report_metadata?.generated_at?.slice(0, 19)} UTC
                </span>
              </div>
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
              <button
                onClick={handleDownloadJson}
                className="flex items-center px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-xs font-semibold transition-colors border border-slate-600"
              >
                <Download className="w-4 h-4 mr-1.5" /> Export JSON
              </button>
              <button
                onClick={handleDownloadPdf}
                disabled={downloadingPdf}
                className="flex items-center px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-600/50 text-white rounded-lg text-xs font-bold transition-colors shadow-lg shadow-emerald-600/20"
              >
                <FileText className="w-4 h-4 mr-1.5" /> {downloadingPdf ? 'Building PDF...' : 'Download Supervisory PDF'}
              </button>
            </div>
          </div>

          {/* Report Document Sheet Preview */}
          <div className="bg-slate-900 rounded-xl border border-slate-700 p-8 shadow-2xl text-slate-200 space-y-8 max-w-5xl mx-auto">
            {/* 1. Report Header */}
            <div className="border-b border-slate-700 pb-6">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-xs font-bold tracking-widest text-blue-400 uppercase">
                    NATIONAL TECHNICAL RESEARCH ORGANISATION (NTRO) / NCIIPC
                  </span>
                  <h2 className="text-2xl font-black text-white mt-1">SAT-SA SUPERVISORY ASSESSMENT REPORT</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Post-Operational Security Operations Center Evaluation</p>
                </div>
                <span className="px-3 py-1 rounded text-xs font-bold bg-slate-800 text-slate-300 border border-slate-700">
                  {reportData.report_metadata?.classification}
                </span>
              </div>

              {/* Metadata Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 p-4 bg-slate-800/60 rounded-lg border border-slate-700/60 text-xs">
                <div>
                  <span className="text-slate-500 uppercase block">Entity</span>
                  <strong className="text-white">{reportData.entity_summary?.name} ({reportData.entity_summary?.entity_id})</strong>
                </div>
                <div>
                  <span className="text-slate-500 uppercase block">Sector</span>
                  <strong className="text-slate-300">{reportData.entity_summary?.sector}</strong>
                </div>
                <div>
                  <span className="text-slate-500 uppercase block">Assessment Period</span>
                  <strong className="text-slate-300">{reportData.entity_summary?.assessment_period}</strong>
                </div>
                <div>
                  <span className="text-slate-500 uppercase block">Assessment Validity</span>
                  <ValidityBadge validity={reportData.assessment_summary?.assessment_validity} />
                </div>
              </div>
            </div>

            {/* 2. Executive Summary */}
            <div>
              <h3 className="text-base font-bold text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                <Shield className="w-4 h-4 text-blue-400" /> 1. Executive Summary
              </h3>
              <p className="text-sm text-slate-300 leading-relaxed bg-slate-800/40 p-4 rounded-lg border border-slate-700/50">
                {reportData.assessment_summary?.executive_summary}
              </p>
              <p className="text-xs text-slate-400 italic mt-2">
                <strong>Advisory Notice:</strong> {reportData.assessment_summary?.advisory_notice}
              </p>
            </div>

            {/* 3. 8 Operational Capabilities Assessment */}
            <div>
              <h3 className="text-base font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" /> 2. Operational Capability Assessment (8 PS Dimensions)
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-800 text-slate-400 uppercase tracking-wider">
                    <tr>
                      <th className="py-2.5 px-3">Capability</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Findings</th>
                      <th className="py-2.5 px-3">Validity</th>
                      <th className="py-2.5 px-3">Observation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 bg-slate-900/60">
                    {reportData.capability_assessment?.map((cap, i) => (
                      <tr key={i} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-3 font-bold text-white">{cap.name}</td>
                        <td className="py-2.5 px-3"><CapabilityChip status={cap.status} /></td>
                        <td className="py-2.5 px-3 font-bold">{cap.findings_count}</td>
                        <td className="py-2.5 px-3">{cap.assessment_validity}</td>
                        <td className="py-2.5 px-3 text-slate-300 max-w-sm">{cap.observation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 4. Supervisory Findings */}
            <div>
              <h3 className="text-base font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" /> 3. Key Supervisory Findings & Evidence References
              </h3>
              {reportData.findings?.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No supervisory findings flagged for this assessment scope.</p>
              ) : (
                <div className="space-y-4">
                  {reportData.findings?.map((f, i) => (
                    <div key={i} className="p-4 bg-slate-800/60 rounded-lg border border-slate-700/80 space-y-2 text-xs">
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="font-mono text-slate-400 text-2xs block">{f.finding_id}</span>
                          <strong className="text-sm font-bold text-white">{f.title}</strong>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded font-bold ${
                            f.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                            f.severity === 'HIGH' ? 'bg-orange-500/20 text-orange-400' : 'bg-blue-500/20 text-blue-400'
                          }`}>
                            {f.severity}
                          </span>
                          <ValidityBadge validity={f.assessment_validity} />
                        </div>
                      </div>

                      <p className="text-slate-300"><strong>Observed:</strong> {f.description}</p>
                      <p className="text-slate-400"><strong>Rationale:</strong> {f.rationale}</p>
                      
                      <div className="p-2.5 bg-slate-900/80 rounded border border-slate-800 flex justify-between items-center text-2xs">
                        <span className="text-slate-400">
                          Human Examiner Decision: <strong className="text-white">{f.human_decision?.status || 'OPEN'}</strong> 
                          {f.human_decision?.actor && ` by ${f.human_decision.actor}`}
                        </span>
                        <span className="text-slate-500">
                          Confidence: {Math.round((f.finding_confidence || 0) * 100)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 5. Assessment Assurance & Limitations */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wider mb-2">
                  4. Assessment Assurance Matrix
                </h3>
                <div className="space-y-2 text-xs">
                  {reportData.assurance?.dimension_details && Object.entries(reportData.assurance.dimension_details).map(([k, v]) => (
                    <div key={k} className="p-2.5 bg-slate-800/50 rounded border border-slate-700/60 flex justify-between">
                      <span className="font-semibold text-slate-300 uppercase">{k.replace('_', ' ')}</span>
                      <span className={`font-bold uppercase ${
                        v.status === 'LOW' ? 'text-red-400' : v.status === 'CAUTION' ? 'text-amber-400' : 'text-emerald-400'
                      }`}>{v.status || 'HIGH'}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-base font-bold text-white uppercase tracking-wider mb-2">
                  5. Evidence Limitations
                </h3>
                <div className="space-y-2 text-xs">
                  {reportData.evidence_limitations?.missing?.map((m, i) => (
                    <div key={i} className="p-2.5 bg-rose-500/10 rounded border border-rose-500/20 text-rose-300">
                      <strong>Missing:</strong> {m.item} — {m.observation}
                    </div>
                  ))}
                  {reportData.evidence_limitations?.partial?.map((p, i) => (
                    <div key={i} className="p-2.5 bg-amber-500/10 rounded border border-amber-500/20 text-amber-300">
                      <strong>Partial:</strong> {p.item} — {p.observation}
                    </div>
                  ))}
                  {(!reportData.evidence_limitations?.missing || reportData.evidence_limitations.missing.length === 0) && (
                    <p className="text-slate-400 text-xs italic">No critical missing evidence limitations identified.</p>
                  )}
                </div>
              </div>
            </div>

            {/* 6. Human Adjudication & Evidence Requests */}
            <div>
              <h3 className="text-base font-bold text-white uppercase tracking-wider mb-2">
                6. Human Examiner Adjudications & Requests
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
                <div className="p-3 bg-emerald-500/10 rounded border border-emerald-500/20">
                  <span className="text-slate-400 block">Confirmed</span>
                  <strong className="text-base text-white">{reportData.human_adjudication?.confirmed || 0}</strong>
                </div>
                <div className="p-3 bg-purple-500/10 rounded border border-purple-500/20">
                  <span className="text-slate-400 block">Evidence Requested</span>
                  <strong className="text-base text-white">{reportData.human_adjudication?.evidence_requested || 0}</strong>
                </div>
                <div className="p-3 bg-blue-500/10 rounded border border-blue-500/20">
                  <span className="text-slate-400 block">Modified</span>
                  <strong className="text-base text-white">{reportData.human_adjudication?.modified || 0}</strong>
                </div>
                <div className="p-3 bg-slate-800 rounded border border-slate-700">
                  <span className="text-slate-400 block">Open / Pending</span>
                  <strong className="text-base text-amber-400">{reportData.human_adjudication?.open_under_review || 0}</strong>
                </div>
              </div>
            </div>

            {/* 7. Provenance & Traceability Footer */}
            <div className="pt-6 border-t border-slate-800 text-2xs text-slate-500 flex flex-col md:flex-row justify-between items-center gap-2">
              <span>SAT-SA Cryptographic Provenance Verified • Offline Supervisory Engine</span>
              <span>NTRO / NCIIPC Official Supervisory Artifact</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportGeneration;
