import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, CheckCircle2, AlertTriangle, XCircle, FileText, Database, ShieldAlert, ArrowRight, Layers } from 'lucide-react';
import api from '../services/api';

const UploadData = () => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);
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
    setErrorMsg(null);
    setValidationResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await api.post('/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setValidationResult(res.data);
    } catch (err) {
      console.error("Upload failed", err);
      setErrorMsg(err.response?.data?.detail || "Failed to upload and validate file. Please check format.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white mb-2">CSE Data Submission</h1>
        <p className="text-slate-400">
          Module 1: Ingest, validate, and normalize periodic SOC alert dumps, asset inventories, or case management exports.
        </p>
      </div>

      {errorMsg && (
        <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg flex items-center text-red-300">
          <XCircle className="w-5 h-5 mr-3 shrink-0 text-red-400" />
          <div className="flex-1 text-sm font-medium">{errorMsg}</div>
          <button 
            onClick={() => setErrorMsg(null)}
            className="text-xs text-red-400 hover:underline ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {!validationResult ? (
        <div 
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-all ${
            dragActive 
              ? 'border-blue-500 bg-blue-500/10 scale-[1.01]' 
              : 'border-slate-600 bg-slate-800 hover:border-slate-500'
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
            accept=".csv,.tsv,.txt,.json,.jsonl"
            onChange={handleChange}
          />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center justify-center">
            {uploading ? (
              <div className="flex flex-col items-center">
                <div className="animate-spin rounded-full h-14 w-14 border-t-2 border-b-2 border-blue-500 mb-4"></div>
                <span className="text-lg font-medium text-white mb-1">Processing and Validating Ingestion...</span>
                <span className="text-slate-400 text-sm">Executing schema detection, normalization, and quality checks</span>
              </div>
            ) : (
              <>
                <FileUp className="w-16 h-16 text-slate-400 mb-4" />
                <span className="text-xl font-medium text-white mb-2">
                  Drag and drop SOC dataset export here
                </span>
                <span className="text-slate-400 text-sm mb-6">
                  Supports CSV, TSV, TXT, or JSON exports (Alerts, Assets, or Cases)
                </span>
                <span className="px-6 py-2.5 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 transition-colors shadow-lg shadow-blue-600/20">
                  Select File from Machine
                </span>
              </>
            )}
          </label>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 shadow-xl">
          {/* Header Banner */}
          <div className="flex items-center justify-between mb-6 pb-6 border-b border-slate-700">
            <div className="flex items-center">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center mr-4 ${
                validationResult.status === 'validated' 
                  ? 'bg-green-500/20 text-green-400' 
                  : validationResult.status === 'validated_with_warnings'
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-red-500/20 text-red-400'
              }`}>
                {validationResult.status === 'validated' && <CheckCircle2 className="w-6 h-6" />}
                {validationResult.status === 'validated_with_warnings' && <AlertTriangle className="w-6 h-6" />}
                {validationResult.status === 'rejected' && <XCircle className="w-6 h-6" />}
              </div>
              <div>
                <h2 className="text-xl font-bold text-white flex items-center">
                  {validationResult.status === 'validated' && 'Ingestion & Validation Successful'}
                  {validationResult.status === 'validated_with_warnings' && 'Validated with Quality Notices'}
                  {validationResult.status === 'rejected' && 'Dataset Rejected - Validation Errors'}
                  <span className={`ml-3 text-xs uppercase px-2.5 py-1 rounded font-bold ${
                    validationResult.status === 'validated'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : validationResult.status === 'validated_with_warnings'
                      ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                      : 'bg-red-500/20 text-red-400 border border-red-500/30'
                  }`}>
                    {validationResult.status.replace(/_/g, ' ')}
                  </span>
                </h2>
                <p className="text-slate-400 text-sm mt-1">
                  Upload ID: <span className="font-mono text-slate-300">{validationResult.upload_id}</span>
                </p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs uppercase text-slate-400 block font-semibold">Dataset Type</span>
              <span className="text-base font-bold text-blue-400 capitalize">{validationResult.dataset_type}</span>
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/60">
              <span className="text-xs text-slate-400 uppercase font-medium">Received Rows</span>
              <p className="text-2xl font-bold text-white mt-1">{validationResult.records_received.toLocaleString()}</p>
            </div>
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/60">
              <span className="text-xs text-slate-400 uppercase font-medium">Valid Records</span>
              <p className="text-2xl font-bold text-green-400 mt-1">{validationResult.records_valid.toLocaleString()}</p>
            </div>
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/60">
              <span className="text-xs text-slate-400 uppercase font-medium">Rejected Records</span>
              <p className={`text-2xl font-bold mt-1 ${validationResult.records_rejected > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                {validationResult.records_rejected.toLocaleString()}
              </p>
            </div>
            <div className="bg-slate-900/60 p-4 rounded-lg border border-slate-700/60">
              <span className="text-xs text-slate-400 uppercase font-medium">Warnings / Errors</span>
              <p className="text-2xl font-bold text-orange-400 mt-1">
                {validationResult.warnings_count} <span className="text-sm text-slate-500 font-normal">/ {validationResult.errors_count}</span>
              </p>
            </div>
          </div>

          {/* Ingestion & Quality Summary */}
          <div className="bg-slate-900/40 rounded-lg p-5 border border-slate-700/50 mb-6 space-y-3 text-sm">
            <h3 className="text-xs uppercase font-bold text-slate-400 tracking-wider mb-3 flex items-center">
              <Database className="w-4 h-4 mr-2 text-blue-400" /> Normalization & Quality Profile
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2 text-slate-300">
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">File Name:</span>
                <span className="font-medium text-white">{validationResult.filename}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Format Detected:</span>
                <span className="font-medium uppercase text-white">{validationResult.file_type}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Entities Detected:</span>
                <span className="font-medium text-white">
                  {validationResult.entities_detected?.length > 0 
                    ? validationResult.entities_detected.join(", ") 
                    : "CSE-001"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Date Range:</span>
                <span className="font-medium text-white">
                  {validationResult.date_range_start 
                    ? `${validationResult.date_range_start.substring(0, 10)} to ${validationResult.date_range_end?.substring(0, 10)}` 
                    : "Single Period / Undated"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Missing Timestamps:</span>
                <span className={validationResult.quality?.missing_timestamps > 0 ? "text-red-400 font-bold" : "text-slate-400"}>
                  {validationResult.quality?.missing_timestamps || 0}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800">
                <span className="text-slate-400">Duplicate IDs Detected:</span>
                <span className={validationResult.quality?.duplicate_ids > 0 ? "text-yellow-400 font-bold" : "text-slate-400"}>
                  {validationResult.quality?.duplicate_ids || 0}
                </span>
              </div>
            </div>

            {/* Detected Columns */}
            <div className="pt-3">
              <span className="text-xs text-slate-400 font-semibold block mb-2">Detected Input Columns:</span>
              <div className="flex flex-wrap gap-1.5">
                {validationResult.columns_detected?.map((col, i) => (
                  <span key={i} className="text-xs bg-slate-800 text-slate-300 px-2.5 py-1 rounded border border-slate-700 font-mono">
                    {col}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-4">
            <button 
              onClick={() => { setValidationResult(null); setFile(null); }}
              className="px-5 py-2.5 border border-slate-600 rounded-md text-slate-300 hover:bg-slate-700 transition-colors text-sm font-medium"
            >
              Upload Another File
            </button>
            <button 
              onClick={() => navigate(`/preview/${validationResult.upload_id}`)}
              className="flex items-center px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-medium transition-colors shadow-lg shadow-blue-600/20 text-sm"
            >
              Continue to Data Preview
              <ArrowRight className="w-4 h-4 ml-2" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadData;
