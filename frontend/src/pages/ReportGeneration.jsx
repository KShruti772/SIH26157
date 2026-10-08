import React, { useState } from 'react';
import { FileText, Download, CheckCircle2, FileBarChart } from 'lucide-react';
import api from '../services/api';

const ReportGeneration = () => {
  const [generating, setGenerating] = useState(false);
  const [reportReady, setReportReady] = useState(false);

  const handleGenerate = () => {
    setGenerating(true);
    setTimeout(() => {
      setGenerating(false);
      setReportReady(true);
    }, 2500);
  };

  return (
    <div className="max-w-4xl mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">Generate Supervisory Report</h1>
        <p className="text-slate-400">Compile findings, risk assessments, and evidence into a formal report.</p>
      </div>

      {!reportReady ? (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 shadow-sm text-center">
          <FileBarChart className="w-16 h-16 text-slate-500 mx-auto mb-6" />
          <h2 className="text-xl font-medium text-white mb-4">Ready to Generate Report</h2>
          <p className="text-slate-400 mb-8 max-w-lg mx-auto">
            The report will include executive summary, assessment scope, entity risks, execution gaps, negative space, peer benchmarking, and audit trail.
          </p>
          <button 
            onClick={handleGenerate}
            disabled={generating}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white px-8 py-3 rounded-lg font-bold transition-colors shadow-lg shadow-blue-600/20"
          >
            {generating ? 'Compiling Data...' : 'Generate Comprehensive Report'}
          </button>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 shadow-sm">
          <div className="flex items-center mb-8 border-b border-slate-700 pb-6">
            <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mr-4 shrink-0">
              <CheckCircle2 className="w-6 h-6 text-green-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Report Generated Successfully</h2>
              <p className="text-slate-400">Supervisory_Assessment_2026-Q3.pdf</p>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-slate-900 p-4 rounded border border-slate-700">
              <h3 className="text-sm font-bold text-slate-400 uppercase mb-2">Included Entities</h3>
              <p className="text-white text-xl">10</p>
            </div>
            <div className="bg-slate-900 p-4 rounded border border-slate-700">
              <h3 className="text-sm font-bold text-slate-400 uppercase mb-2">Total Findings</h3>
              <p className="text-white text-xl">42</p>
            </div>
          </div>

          <div className="flex justify-end space-x-4">
            <button className="flex items-center px-6 py-2 border border-slate-600 rounded text-slate-300 hover:bg-slate-700 transition-colors">
              <FileText className="w-4 h-4 mr-2" /> Preview
            </button>
            <button className="flex items-center px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors shadow-lg shadow-blue-600/20">
              <Download className="w-4 h-4 mr-2" /> Download PDF
            </button>
            <button className="flex items-center px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-medium transition-colors border border-slate-600">
              <Download className="w-4 h-4 mr-2" /> Export JSON
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportGeneration;
