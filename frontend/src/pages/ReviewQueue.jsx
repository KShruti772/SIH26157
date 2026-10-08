import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Eye, UserPlus, CheckSquare, XSquare, ExternalLink } from 'lucide-react';
import api from '../services/api';

const ReviewQueue = () => {
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchQueue();
  }, []);

  const fetchQueue = async () => {
    try {
      const res = await api.get('/review-queue');
      setQueue(res.data.sort((a, b) => b.review_item.priority_score - a.review_item.priority_score));
    } catch (err) {
      console.error(err);
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
    const reviewer = prompt("Enter reviewer username:");
    if (reviewer) {
      try {
        await api.patch(`/review-queue/${id}`, { status: 'Assigned', reviewer });
        fetchQueue();
      } catch (err) {
        console.error(err);
      }
    }
  };

  if (loading) return <div className="text-white p-8">Loading review queue...</div>;

  return (
    <div className="max-w-7xl mx-auto flex flex-col h-full">
      <div className="mb-6 shrink-0">
        <h1 className="text-2xl font-bold text-white mb-2">Priority Manual Review Queue</h1>
        <p className="text-slate-400">Queue for human supervisors to validate analytics findings.</p>
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-auto p-6">
          <div className="space-y-4">
            {queue.map((item, index) => (
              <div key={item.review_item.id} className="bg-slate-900 border border-slate-700 rounded-lg p-5 relative overflow-hidden">
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${
                  item.review_item.priority_score > 90 ? 'bg-red-500' :
                  item.review_item.priority_score > 75 ? 'bg-orange-500' :
                  'bg-yellow-500'
                }`}></div>
                
                <div className="flex justify-between items-start mb-4 pl-3">
                  <div>
                    <div className="flex items-center mb-1">
                      <span className="text-sm font-bold text-slate-300 mr-3">Priority #{index + 1}</span>
                      <Link to={`/entity/${item.finding.entity_id}`} className="text-xs bg-slate-800 text-slate-400 px-2 py-1 rounded border border-slate-700 hover:text-white transition-colors">
                        Entity: {item.finding.entity_id}
                      </Link>
                    </div>
                    <h3 className="text-lg font-medium text-white">{item.finding.type}</h3>
                  </div>
                  
                  <div className="text-right">
                    <p className="text-xs text-slate-400 mb-1">Priority Score</p>
                    <div className="text-2xl font-bold text-white">
                      {item.review_item.priority_score.toFixed(0)}<span className="text-sm text-slate-500">/100</span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-4 mb-4 pl-3">
                  <div>
                    <p className="text-xs text-slate-500">Risk</p>
                    <p className={`text-sm font-bold ${
                      item.finding.severity === 'CRITICAL' ? 'text-red-400' :
                      item.finding.severity === 'HIGH' ? 'text-orange-400' : 'text-yellow-400'
                    }`}>{item.finding.severity}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Confidence</p>
                    <p className="text-sm text-white font-medium">{(item.finding.confidence * 100).toFixed(0)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Category</p>
                    <p className="text-sm text-slate-300 capitalize">{item.finding.category.replace('_', ' ')}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Status</p>
                    <p className="text-sm text-blue-400">{item.review_item.status}</p>
                    {item.review_item.reviewer && <p className="text-xs text-slate-500">({item.review_item.reviewer})</p>}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 pt-4 border-t border-slate-800 pl-3">
                  <Link 
                    to={`/findings/${item.finding.id}`}
                    className="flex items-center text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded border border-slate-700 transition-colors"
                  >
                    <Eye className="w-4 h-4 mr-1.5" /> View Finding
                  </Link>
                  <Link 
                    to={`/evidence/${item.finding.id}`}
                    className="flex items-center text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded border border-slate-700 transition-colors"
                  >
                    <ExternalLink className="w-4 h-4 mr-1.5" /> View Evidence
                  </Link>
                  <button 
                    onClick={() => handleAssign(item.review_item.id)}
                    className="flex items-center text-xs font-medium text-blue-300 bg-blue-900/30 hover:bg-blue-900/50 px-3 py-1.5 rounded border border-blue-800 transition-colors"
                  >
                    <UserPlus className="w-4 h-4 mr-1.5" /> Assign
                  </button>
                  <div className="flex-1"></div>
                  <button 
                    onClick={() => handleUpdateStatus(item.review_item.id, 'Reviewed')}
                    className="flex items-center text-xs font-medium text-green-400 bg-green-900/20 hover:bg-green-900/40 px-3 py-1.5 rounded border border-green-800 transition-colors"
                  >
                    <CheckSquare className="w-4 h-4 mr-1.5" /> Mark Reviewed
                  </button>
                  <button 
                    onClick={() => handleUpdateStatus(item.review_item.id, 'Dismissed')}
                    className="flex items-center text-xs font-medium text-slate-400 hover:text-red-400 px-3 py-1.5 transition-colors"
                  >
                    <XSquare className="w-4 h-4 mr-1.5" /> Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReviewQueue;
