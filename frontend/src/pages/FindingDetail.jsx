import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, ShieldAlert, AlertCircle, PlusCircle } from 'lucide-react';
import api from '../services/api';

const FindingDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [finding, setFinding] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFinding = async () => {
      try {
        const res = await api.get(`/findings/${id}`);
        setFinding(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchFinding();
  }, [id]);

  const handleAddToReview = async () => {
    try {
      // Simulate adding to review queue
      await api.patch(`/review-queue/1`, { status: 'Pending' });
      navigate('/review-queue');
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="text-white p-8">Loading explanation...</div>;
  if (!finding) return <div className="text-white p-8">Finding not found.</div>;

  return (
    <div className="max-w-4xl mx-auto py-4">
      <button 
        onClick={() => navigate(-1)}
        className="flex items-center text-slate-400 hover:text-white mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-2" /> Back to Findings
      </button>

      <div className="bg-slate-800 rounded-xl border border-slate-700 shadow-xl overflow-hidden">
        <div className="bg-slate-900/50 p-6 border-b border-slate-700">
          <div className="flex justify-between items-start mb-4">
            <h1 className="text-xl font-bold text-slate-300 tracking-wider">WHY WAS THIS FLAGGED?</h1>
            <span className={`px-3 py-1 rounded text-xs font-bold ${
              finding.severity === 'CRITICAL' ? 'bg-red-500 text-white' :
              finding.severity === 'HIGH' ? 'bg-orange-500 text-white' :
              'bg-yellow-500 text-white'
            }`}>
              {finding.severity}
            </span>
          </div>
          
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-slate-500 text-xs mb-1 uppercase">Finding Type</p>
              <p className="text-white text-lg font-medium">{finding.type}</p>
            </div>
            <div>
              <p className="text-slate-500 text-xs mb-1 uppercase">Affected Entity</p>
              <Link to={`/entity/${finding.entity_id}`} className="text-blue-400 hover:underline flex items-center text-lg font-medium">
                {finding.entity_id} <ExternalLink className="w-4 h-4 ml-2" />
              </Link>
            </div>
          </div>
          
          <div className="bg-slate-800 p-4 rounded border border-slate-700">
            <p className="text-slate-300">{finding.description}</p>
          </div>
        </div>

        <div className="p-6 border-b border-slate-700">
          <h2 className="text-sm font-bold text-slate-400 tracking-wider mb-4 uppercase flex items-center">
            <AlertCircle className="w-4 h-4 mr-2" /> Rule / Analytic Used
          </h2>
          <div className="bg-slate-900 p-4 rounded text-slate-300 border border-slate-700 font-mono text-sm">
            {finding.category === 'execution_gap' && 'Rule: Critical Alert Escalation'}
            {finding.category === 'negative_space' && 'Rule: Critical Asset Telemetry Monitoring'}
            {finding.category === 'anomaly' && 'Model: Isolation Forest Anomaly Detection'}
            
            <div className="mt-4 text-slate-400">
              <span className="text-slate-500">Threshold:</span> {finding.rationale}
            </div>
          </div>
        </div>

        <div className="p-6 border-b border-slate-700">
          <h2 className="text-sm font-bold text-slate-400 tracking-wider mb-4 uppercase">Observed Data & Why It Matters</h2>
          <div className="bg-slate-800/50 p-5 rounded border border-slate-700">
            <div className="mb-4 text-slate-300">
              {finding.category === 'execution_gap' && (
                <ul className="space-y-2 font-mono text-sm">
                  <li>Critical alerts: <span className="text-white">43</span></li>
                  <li>Escalated: <span className="text-white">5</span></li>
                  <li>Not escalated: <span className="text-red-400">38</span></li>
                  <li className="pt-2 border-t border-slate-700">Escalation rate: <span className="text-red-400">11.6%</span></li>
                  <li>Peer median: <span className="text-green-400">84%</span></li>
                  <li>Deviation: <span className="text-orange-400">-72.4%</span></li>
                </ul>
              )}
              {finding.category === 'negative_space' && (
                <ul className="space-y-2 font-mono text-sm">
                  <li>Critical assets total: <span className="text-white">12</span></li>
                  <li>Assets with active telemetry: <span className="text-white">8</span></li>
                  <li>Missing expected evidence: <span className="text-red-400">4 assets</span></li>
                </ul>
              )}
            </div>
            <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-md">
              <p className="text-orange-300 text-sm">
                The entity shows a significant deviation from peer behaviour and requires supervisory validation.
              </p>
            </div>
          </div>
        </div>

        <div className="p-6 border-b border-slate-700 bg-slate-900/30">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-sm font-bold text-slate-400 tracking-wider uppercase">Supporting Evidence</h2>
            <Link 
              to={`/evidence/${finding.id}`}
              className="text-sm text-blue-400 hover:text-blue-300 flex items-center"
            >
              View in Evidence Explorer <ExternalLink className="w-4 h-4 ml-1" />
            </Link>
          </div>
          
          {finding.evidence_ids && finding.evidence_ids.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {finding.evidence_ids.map(id => (
                <span key={id} className="px-3 py-1 bg-slate-800 border border-slate-600 rounded text-sm text-slate-300 font-mono">
                  {id}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm italic">Absence of expected evidence (Negative Space indicator).</p>
          )}
        </div>

        <div className="p-6 bg-slate-800">
          <h2 className="text-sm font-bold text-slate-400 tracking-wider mb-4 uppercase">Recommended Supervisory Action</h2>
          <div className="flex justify-between items-center bg-blue-900/20 border border-blue-500/30 p-4 rounded-lg">
            <div className="flex items-start">
              <ShieldAlert className="w-6 h-6 text-blue-400 mr-3 shrink-0" />
              <p className="text-slate-200">{finding.recommended_action}</p>
            </div>
            <button 
              onClick={handleAddToReview}
              className="ml-6 flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors shrink-0 whitespace-nowrap"
            >
              <PlusCircle className="w-4 h-4 mr-2" /> Add to Review Queue
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FindingDetail;
