import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ShieldOff, Activity, Users, Search, Filter, ChevronRight } from 'lucide-react';
import api from '../services/api';

const colorClasses = {
  red: { bg: 'bg-red-500/10', border: 'border-red-500', text: 'text-red-400' },
  orange: { bg: 'bg-orange-500/10', border: 'border-orange-500', text: 'text-orange-400' },
  yellow: { bg: 'bg-yellow-500/10', border: 'border-yellow-500', text: 'text-yellow-400' },
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500', text: 'text-blue-400' },
};

const CategoryCard = ({ title, icon: Icon, count, active, onClick, color }) => (
  <button 
    onClick={onClick}
    className={`p-4 rounded-lg border text-left transition-all ${
      active 
        ? `bg-slate-700 ${colorClasses[color].border} shadow-md` 
        : 'bg-slate-800 border-slate-700 hover:bg-slate-750'
    }`}
  >
    <div className="flex items-center justify-between mb-2">
      <div className={`p-2 rounded-md bg-slate-800 border border-slate-600 ${colorClasses[color].text}`}>
        <Icon className="w-5 h-5" />
      </div>
      <span className="text-2xl font-bold text-white">{count}</span>
    </div>
    <h3 className="font-medium text-slate-200">{title}</h3>
  </button>
);

const Findings = () => {
  const [findings, setFindings] = useState([]);
  const [activeTab, setActiveTab] = useState('execution_gap');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchFindings = async () => {
      try {
        const res = await api.get('/findings');
        setFindings(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchFindings();
  }, []);

  const counts = {
    execution_gap: findings.filter(f => f.category === 'execution_gap').length,
    negative_space: findings.filter(f => f.category === 'negative_space').length,
    anomaly: findings.filter(f => f.category === 'anomaly').length,
    peer_deviation: findings.filter(f => f.category === 'peer_deviation').length,
  };

  const activeFindings = findings.filter(f => f.category === activeTab);

  if (loading) return <div className="text-white p-8">Loading findings...</div>;

  return (
    <div className="max-w-7xl mx-auto h-full flex flex-col">
      <div className="mb-6 shrink-0">
        <h1 className="text-2xl font-bold text-white mb-2">Supervisory Findings</h1>
        <p className="text-slate-400">Review analytical results across four main categories.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 shrink-0">
        <CategoryCard 
          title="Execution Gaps" 
          count={counts.execution_gap} 
          icon={AlertTriangle} 
          active={activeTab === 'execution_gap'} 
          onClick={() => setActiveTab('execution_gap')}
          color="red"
        />
        <CategoryCard 
          title="Negative Space" 
          count={counts.negative_space} 
          icon={ShieldOff} 
          active={activeTab === 'negative_space'} 
          onClick={() => setActiveTab('negative_space')}
          color="orange"
        />
        <CategoryCard 
          title="Anomalies" 
          count={counts.anomaly} 
          icon={Activity} 
          active={activeTab === 'anomaly'} 
          onClick={() => setActiveTab('anomaly')}
          color="yellow"
        />
        <CategoryCard 
          title="Peer Deviations" 
          count={counts.peer_deviation} 
          icon={Users} 
          active={activeTab === 'peer_deviation'} 
          onClick={() => setActiveTab('peer_deviation')}
          color="blue"
        />
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 flex flex-col overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50 shrink-0">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search findings..." 
              className="pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded text-sm text-white focus:outline-none focus:border-blue-500 w-64"
            />
          </div>
          <button className="flex items-center text-sm text-slate-300 bg-slate-700 px-3 py-2 rounded hover:bg-slate-600 transition-colors">
            <Filter className="w-4 h-4 mr-2" /> Filter
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4">
          <div className="space-y-4">
            {activeFindings.length === 0 ? (
              <div className="text-center py-12 text-slate-400">No findings in this category.</div>
            ) : (
              activeFindings.map((finding) => (
                <div 
                  key={finding.id} 
                  className="bg-slate-700/30 border border-slate-700 rounded-lg p-5 hover:border-slate-500 transition-colors cursor-pointer group"
                  onClick={() => navigate(`/findings/${finding.id}`)}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="flex items-center mb-2">
                        <span className="font-mono text-xs text-blue-400 bg-blue-400/10 px-2 py-1 rounded mr-3">
                          {finding.id}
                        </span>
                        <span className="text-xs text-slate-400 mr-3">Entity: <span className="text-slate-200 font-medium">{finding.entity_id}</span></span>
                        <span className={`text-xs font-bold px-2 py-1 rounded ${
                          finding.severity === 'CRITICAL' ? 'bg-red-500 text-white' :
                          finding.severity === 'HIGH' ? 'bg-orange-500 text-white' :
                          'bg-yellow-500 text-white'
                        }`}>
                          {finding.severity}
                        </span>
                      </div>
                      <h4 className="text-lg font-medium text-white mb-2">{finding.type}</h4>
                      <p className="text-slate-400 text-sm mb-4 line-clamp-2">{finding.description}</p>
                    </div>
                    <div className="bg-slate-800 p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity">
                      <ChevronRight className="w-5 h-5 text-blue-400" />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4 border-t border-slate-600 pt-4 mt-2">
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Confidence</p>
                      <p className="text-sm font-medium text-white">{(finding.confidence * 100).toFixed(0)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Risk Contribution</p>
                      <p className="text-sm font-medium text-white">{finding.risk_contribution} / 100</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 mb-1">Status</p>
                      <p className="text-sm font-medium text-blue-400">{finding.status}</p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Findings;
