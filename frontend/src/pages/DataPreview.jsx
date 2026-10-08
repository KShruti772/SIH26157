import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Play, Search, Filter } from 'lucide-react';
import api from '../services/api';

const DataPreview = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await api.get(`/upload/${id}/preview`);
        setData(res.data.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleRunAnalysis = async () => {
    try {
      const res = await api.post('/analysis/run');
      navigate(`/analysis/${res.data.analysis_id}`);
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="text-white p-8">Loading preview...</div>;

  return (
    <div className="max-w-7xl mx-auto flex flex-col h-full">
      <div className="flex justify-between items-center mb-6 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-white mb-2">Data Preview</h1>
          <p className="text-slate-400">Step 2: Verify data fields before running supervisory analysis.</p>
        </div>
        <button 
          onClick={handleRunAnalysis}
          className="flex items-center bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-md font-bold transition-colors shadow-lg shadow-blue-600/20"
        >
          <Play className="w-5 h-5 mr-2" fill="currentColor" />
          Run Supervisory Analysis
        </button>
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 flex flex-col flex-1 overflow-hidden">
        <div className="p-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50 shrink-0">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input 
              type="text" 
              placeholder="Search records..." 
              className="pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded text-sm text-white focus:outline-none focus:border-blue-500 w-64"
            />
          </div>
          <button className="flex items-center text-sm text-slate-300 bg-slate-700 px-3 py-2 rounded hover:bg-slate-600 transition-colors">
            <Filter className="w-4 h-4 mr-2" /> Filter Columns
          </button>
        </div>
        
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-900/50 sticky top-0 z-10 text-xs uppercase text-slate-400 font-semibold border-b border-slate-700">
              <tr>
                <th className="p-4">Alert ID</th>
                <th className="p-4">Entity ID</th>
                <th className="p-4">Timestamp</th>
                <th className="p-4">Severity</th>
                <th className="p-4">Category</th>
                <th className="p-4">Acknowledged</th>
                <th className="p-4">Escalated</th>
                <th className="p-4">Disposition</th>
              </tr>
            </thead>
            <tbody className="text-sm divide-y divide-slate-700/50 text-slate-300">
              {data.map((row, i) => (
                <tr key={i} className="hover:bg-slate-700/30 transition-colors">
                  <td className="p-4 font-mono text-xs">{row.id}</td>
                  <td className="p-4">{row.entity_id}</td>
                  <td className="p-4">{new Date(row.timestamp).toLocaleString()}</td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      row.severity === 'Critical' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                      row.severity === 'High' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20' :
                      row.severity === 'Medium' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                      'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                    }`}>
                      {row.severity}
                    </span>
                  </td>
                  <td className="p-4">{row.category}</td>
                  <td className="p-4">{row.acknowledged ? 'Yes' : 'No'}</td>
                  <td className="p-4">{row.escalated ? 'Yes' : 'No'}</td>
                  <td className="p-4">{row.disposition || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="p-4 border-t border-slate-700 flex justify-between items-center text-sm text-slate-400 bg-slate-800/50 shrink-0">
          <div>Showing 1 to {data.length} of {data.length} records</div>
          <div className="flex space-x-2">
            <button className="px-3 py-1 border border-slate-600 rounded hover:bg-slate-700 disabled:opacity-50">Previous</button>
            <button className="px-3 py-1 border border-slate-600 rounded hover:bg-slate-700">Next</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataPreview;
