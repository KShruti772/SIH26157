import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileUp, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const UploadData = () => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const navigate = useNavigate();

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (selectedFile) => {
    setFile(selectedFile);
    setUploading(true);
    
    // Simulate upload
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
      // For demo, we just call the endpoint.
      // In real life, we might need a real dummy file.
      const blob = new Blob(["dummy content"], { type: "text/csv" });
      formData.set('file', blob, selectedFile.name);
      
      const res = await api.post('/upload', formData);
      
      // Simulate validation result
      setTimeout(() => {
        setValidationResult({
          upload_id: res.data.upload_id,
          filename: selectedFile.name,
          size: `${(selectedFile.size / 1024).toFixed(1)} KB`,
          format: 'CSV',
          records: 10500,
          dateRange: '2026-09-01 to 2026-09-30',
          entities: 10,
          status: 'success'
        });
        setUploading(false);
      }, 1500);
      
    } catch (err) {
      console.error(err);
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">Upload SOC Data</h1>
        <p className="text-slate-400">Step 1: Upload periodic alert and case management data for analysis.</p>
      </div>

      {!validationResult ? (
        <div 
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
            dragActive ? 'border-blue-500 bg-blue-500/10' : 'border-slate-600 bg-slate-800 hover:bg-slate-800/80'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".csv,.json"
            onChange={handleChange}
          />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center">
            {uploading ? (
              <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500 mb-6"></div>
            ) : (
              <FileUp className="w-16 h-16 text-slate-400 mb-6" />
            )}
            
            <span className="text-xl font-medium text-white mb-2">
              {uploading ? 'Processing File...' : 'Drag and drop your file here'}
            </span>
            <span className="text-slate-400 text-sm mb-6">
              {uploading ? 'Validating schema and contents' : 'Supports CSV or JSON exports from SOC platforms'}
            </span>
            
            {!uploading && (
              <span className="px-6 py-2 bg-slate-700 text-white rounded-md font-medium hover:bg-slate-600 transition-colors">
                Browse Files
              </span>
            )}
          </label>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 shadow-sm">
          <div className="flex items-center mb-6 pb-6 border-b border-slate-700">
            <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mr-4">
              <CheckCircle2 className="w-6 h-6 text-green-500" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Data validation successful</h2>
              <p className="text-slate-400 text-sm">The uploaded dataset meets all schema requirements.</p>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-x-8 gap-y-4 mb-8">
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">File Name</span>
              <span className="text-white font-medium">{validationResult.filename}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Format</span>
              <span className="text-white font-medium">{validationResult.format}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">File Size</span>
              <span className="text-white font-medium">{validationResult.size}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Date Range</span>
              <span className="text-white font-medium">{validationResult.dateRange}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Total Records</span>
              <span className="text-white font-medium">{validationResult.records.toLocaleString()}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Entities Detected</span>
              <span className="text-white font-medium">{validationResult.entities}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Missing Fields</span>
              <span className="text-green-400 font-medium">0</span>
            </div>
            <div className="flex justify-between py-2 border-b border-slate-700/50">
              <span className="text-slate-400">Duplicate Records</span>
              <span className="text-green-400 font-medium">0</span>
            </div>
          </div>
          
          <div className="flex justify-end space-x-4">
            <button 
              onClick={() => { setValidationResult(null); setFile(null); }}
              className="px-4 py-2 border border-slate-600 rounded text-slate-300 hover:bg-slate-700 transition-colors"
            >
              Upload Different File
            </button>
            <button 
              onClick={() => navigate(`/preview/${validationResult.upload_id}`)}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium transition-colors shadow-lg shadow-blue-600/20"
            >
              Continue to Data Preview
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadData;
