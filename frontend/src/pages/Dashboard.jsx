import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertTriangle, ShieldAlert, CheckCircle2, Upload, Server, Users, FileBarChart } from 'lucide-react';
import api from '../services/api';

const StatCard = ({ title, value, icon: Icon, color }) => (
  <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 shadow-sm relative overflow-hidden group">
    <div className={`absolute -right-6 -top-6 w-24 h-24 rounded-full opacity-10 transition-transform group-hover:scale-110 ${color}`}></div>
    <div className="flex justify-between items-start relative z-10">
      <div>
        <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
        <h3 className="text-3xl font-bold text-white">{value}</h3>
      </div>
      <div className={`p-3 rounded-md bg-slate-700/50 ${color}`}>
        <Icon className="w-6 h-6" />
      </div>
    </div>
  </div>
);

const Dashboard = () => {
  const [stats, setStats] = useState({
    entities_analyzed: 0,
    findings_generated: 0,
    high_risk_entities: 0,
    priority_reviews: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const res = await api.get('/dashboard');
        setStats(res.data);
      } catch (err) {
        console.error("Failed to load dashboard", err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-slate-400">Loading dashboard...</div>;
  }

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Supervisory Overview</h1>
          <p className="text-slate-400 text-sm">Monitor overall security operations center assessment health.</p>
        </div>
        <Link 
          to="/upload" 
          className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors shadow-lg shadow-blue-600/20"
        >
          <Upload className="w-4 h-4 mr-2" />
          Upload New SOC Data
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard 
          title="Entities Analyzed" 
          value={stats.entities_analyzed} 
          icon={Server} 
          color="text-blue-400 bg-blue-400" 
        />
        <StatCard 
          title="Findings Generated" 
          value={stats.findings_generated} 
          icon={Activity} 
          color="text-indigo-400 bg-indigo-400" 
        />
        <StatCard 
          title="High Risk Entities" 
          value={stats.high_risk_entities} 
          icon={ShieldAlert} 
          color="text-red-400 bg-red-400" 
        />
        <StatCard 
          title="Priority Reviews" 
          value={stats.priority_reviews} 
          icon={AlertTriangle} 
          color="text-orange-400 bg-orange-400" 
        />
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 shadow-sm mb-8">
        <h2 className="text-lg font-medium text-white mb-6">Workflow Progress</h2>
        <div className="relative">
          <div className="absolute top-1/2 left-0 w-full h-1 bg-slate-700 -translate-y-1/2 z-0 rounded"></div>
          
          <div className="relative z-10 flex justify-between">
            {['Upload Data', 'Analyze', 'Gap Detection', 'Risk Assessment', 'Prioritization', 'Report'].map((step, i) => (
              <div key={i} className="flex flex-col items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border-4 border-slate-800 shadow-md ${i < 3 ? 'bg-blue-500 text-white' : 'bg-slate-700 text-slate-400'}`}>
                  {i < 3 ? <CheckCircle2 className="w-5 h-5" /> : <span>{i + 1}</span>}
                </div>
                <span className={`text-xs mt-3 font-medium ${i < 3 ? 'text-blue-400' : 'text-slate-500'}`}>{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4">
             <h2 className="text-lg font-medium text-white">Recent Priority Reviews</h2>
             <Link to="/review-queue" className="text-sm text-blue-400 hover:text-blue-300">View All</Link>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded border border-slate-700/50">
              <div className="flex items-center">
                <div className="w-2 h-2 rounded-full bg-red-500 mr-3"></div>
                <div>
                  <p className="text-sm font-medium text-white">Critical alerts closed without escalation</p>
                  <p className="text-xs text-slate-400">CSE-003 • Execution Gap</p>
                </div>
              </div>
              <span className="text-xs font-semibold bg-red-500/10 text-red-400 px-2 py-1 rounded">Score: 94</span>
            </div>
            <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded border border-slate-700/50">
              <div className="flex items-center">
                <div className="w-2 h-2 rounded-full bg-red-500 mr-3"></div>
                <div>
                  <p className="text-sm font-medium text-white">Missing Telemetry on Critical Assets</p>
                  <p className="text-xs text-slate-400">CSE-005 • Negative Space</p>
                </div>
              </div>
              <span className="text-xs font-semibold bg-red-500/10 text-red-400 px-2 py-1 rounded">Score: 88</span>
            </div>
          </div>
        </div>
        
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 shadow-sm">
          <div className="flex justify-between items-center mb-4">
             <h2 className="text-lg font-medium text-white">Quick Actions</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
             <Link to="/benchmarks" className="p-4 bg-slate-700/50 hover:bg-slate-700 rounded border border-slate-600 transition-colors flex flex-col items-center justify-center text-center">
               <Users className="w-6 h-6 text-blue-400 mb-2" />
               <span className="text-sm font-medium text-white">Peer Benchmarking</span>
             </Link>
             <Link to="/reports" className="p-4 bg-slate-700/50 hover:bg-slate-700 rounded border border-slate-600 transition-colors flex flex-col items-center justify-center text-center">
               <FileBarChart className="w-6 h-6 text-indigo-400 mb-2" />
               <span className="text-sm font-medium text-white">Generate Report</span>
             </Link>
          </div>
        </div>
      </div>
      
    </div>
  );
};

export default Dashboard;
