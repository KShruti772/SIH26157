import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import UploadData from './pages/UploadData';
import DataPreview from './pages/DataPreview';
import AnalysisEngine from './pages/AnalysisEngine';
import Findings from './pages/Findings';
import FindingDetail from './pages/FindingDetail';
import ReviewQueue from './pages/ReviewQueue';
import EvidenceExplorer from './pages/EvidenceExplorer';
import EntityDetail from './pages/EntityDetail';
import Benchmarks from './pages/Benchmarks';
import ReportGeneration from './pages/ReportGeneration';

const PrivateRoute = ({ children }) => {
  const token = localStorage.getItem('token');
  return token ? <Layout>{children}</Layout> : <Navigate to="/login" />;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/upload" element={<PrivateRoute><UploadData /></PrivateRoute>} />
        <Route path="/preview/:id" element={<PrivateRoute><DataPreview /></PrivateRoute>} />
        <Route path="/analysis/:id" element={<PrivateRoute><AnalysisEngine /></PrivateRoute>} />
        <Route path="/findings" element={<PrivateRoute><Findings /></PrivateRoute>} />
        <Route path="/findings/:id" element={<PrivateRoute><FindingDetail /></PrivateRoute>} />
        <Route path="/review-queue" element={<PrivateRoute><ReviewQueue /></PrivateRoute>} />
        <Route path="/evidence/:findingId" element={<PrivateRoute><EvidenceExplorer /></PrivateRoute>} />
        <Route path="/entity/:id" element={<PrivateRoute><EntityDetail /></PrivateRoute>} />
        <Route path="/benchmarks" element={<PrivateRoute><Benchmarks /></PrivateRoute>} />
        <Route path="/reports" element={<PrivateRoute><ReportGeneration /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
