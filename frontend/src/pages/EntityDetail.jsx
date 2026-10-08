import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Building2, ShieldAlert, Activity } from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';
import api from '../services/api';

const EntityDetail = () => {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEntity = async () => {
      try {
        const res = await api.get(`/entities/${id}`);
        setData(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEntity();
  }, [id]);

  if (loading) return <div className="text-white p-8">Loading entity details...</div>;
  if (!data) return <div className="text-white p-8">Entity not found.</div>;

  const { entity, risk } = data;

  const categories = [
    { name: 'Threat Detection', score: 85, status: 'Good' },
    { name: 'Investigation', score: risk ? 100 - risk.investigation_risk * 2 : 80, status: 'Needs Review' },
    { name: 'Escalation', score: risk ? 100 - risk.escalation_risk * 2 : 75, status: 'Warning' },
    { name: 'Incident Response', score: 90, status: 'Good' },
    { name: 'Security Operations', score: risk ? 100 - risk.execution_gap_risk * 2 : 88, status: 'Warning' },
    { name: 'Governance', score: 95, status: 'Good' },
    { name: 'Operational Discipline', score: 70, status: 'Needs Review' },
    { name: 'Cyber Resilience', score: 82, status: 'Good' }
  ];

  return (
    <div className="max-w-7xl mx-auto py-4">
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-sm mb-6 flex justify-between items-center">
        <div className="flex items-center">
          <div className="w-16 h-16 bg-blue-900/50 rounded-lg border border-blue-500 flex items-center justify-center mr-6">
            <Building2 className="w-8 h-8 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">{entity.name} ({entity.id})</h1>
            <p className="text-slate-400">Sector: {entity.sector} • Assessment Period: {entity.assessment_period}</p>
          </div>
        </div>
        
        <div className="text-center">
          <p className="text-slate-400 text-sm mb-1 uppercase tracking-wider">Overall Supervisory Risk</p>
          <div className="flex items-end justify-center">
            <span className={`text-4xl font-bold ${
              risk?.overall_score > 50 ? 'text-red-500' : 
              risk?.overall_score > 25 ? 'text-orange-400' : 'text-green-500'
            }`}>
              {risk?.overall_score || 0}
            </span>
            <span className="text-slate-500 ml-1 text-lg">/ 100</span>
          </div>
          <p className={`text-xs font-medium mt-1 px-2 py-0.5 rounded inline-block ${
            risk?.overall_score > 50 ? 'bg-red-500/20 text-red-400' : 
            risk?.overall_score > 25 ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'
          }`}>
            {risk?.overall_score > 75 ? 'CRITICAL' : risk?.overall_score > 50 ? 'HIGH' : risk?.overall_score > 25 ? 'MODERATE' : 'LOW'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {categories.map(cat => (
          <div key={cat.name} className="bg-slate-800 rounded-lg border border-slate-700 p-4 shadow-sm">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-sm font-medium text-slate-300">{cat.name}</h3>
              <span className={`w-2 h-2 rounded-full ${
                cat.status === 'Good' ? 'bg-green-500' :
                cat.status === 'Warning' ? 'bg-orange-500' : 'bg-red-500'
              }`}></span>
            </div>
            <div className="flex items-end mb-2">
              <span className="text-2xl font-bold text-white leading-none">{cat.score}</span>
              <span className="text-xs text-slate-500 ml-1 mb-0.5">/100</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-1.5 mt-2">
              <div 
                className={`h-1.5 rounded-full ${
                  cat.status === 'Good' ? 'bg-green-500' :
                  cat.status === 'Warning' ? 'bg-orange-500' : 'bg-red-500'
                }`}
                style={{ width: `${cat.score}%` }}
              ></div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 shadow-sm">
          <h2 className="text-lg font-bold text-white mb-4 flex items-center">
            <ShieldAlert className="w-5 h-5 mr-2 text-slate-400" />
            Risk Breakdown
          </h2>
          {risk ? (
            <div className="space-y-4">
              <div className="h-64 mb-4">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                    { subject: 'Execution Gap', A: risk.execution_gap_risk, fullMark: 30 },
                    { subject: 'Negative Space', A: risk.negative_space_risk, fullMark: 30 },
                    { subject: 'Investigation', A: risk.investigation_risk, fullMark: 20 },
                    { subject: 'Escalation', A: risk.escalation_risk, fullMark: 20 },
                    { subject: 'Anomaly', A: risk.anomaly_risk, fullMark: 15 },
                  ]}>
                    <PolarGrid stroke="#475569" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                    <Radar name="Risk" dataKey="A" stroke="#f87171" fill="#ef4444" fillOpacity={0.4} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-between items-center pt-2 mt-4 border-t border-slate-700 font-bold">
                <span className="text-slate-200">Total Supervisory Risk</span>
                <span className="text-blue-400 font-mono text-xl">{risk.overall_score}</span>
              </div>
            </div>
          ) : (
            <p className="text-slate-400">No risk data available.</p>
          )}
        </div>

        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 shadow-sm">
           <h2 className="text-lg font-bold text-white mb-4 flex items-center">
            <Activity className="w-5 h-5 mr-2 text-slate-400" />
            Actionable Next Steps
          </h2>
          <div className="space-y-4">
            <div className="p-4 bg-slate-700/30 rounded border border-slate-700">
              <p className="text-sm text-slate-300">Review findings in the Priority Manual Review queue for this entity.</p>
            </div>
            <div className="p-4 bg-slate-700/30 rounded border border-slate-700">
              <p className="text-sm text-slate-300">Generate Supervisory Report and include specific execution gaps identified.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EntityDetail;
