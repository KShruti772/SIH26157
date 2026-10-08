import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, Upload, Search, Activity, FileText, 
  AlertTriangle, Eye, Users, FileBarChart, LogOut, History,
  ShieldCheck, ShieldAlert
} from 'lucide-react';
import api from '../services/api';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/upload', label: 'Upload Data', icon: Upload },
  { path: '/findings', label: 'Supervisory Findings', icon: AlertTriangle },
  { path: '/review-queue', label: 'Review Queue', icon: Eye },
  { path: '/benchmarks', label: 'Peer Benchmarking', icon: Users },
  { path: '/reports', label: 'Reports', icon: FileBarChart },
  { path: '/audit-replay', label: 'Audit & Replay', icon: History },
];

const Layout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const cached = localStorage.getItem('user');
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    let isMounted = true;
    const fetchUser = async () => {
      try {
        const res = await api.get('/auth/me');
        if (isMounted && res.data) {
          setCurrentUser(res.data);
          localStorage.setItem('user', JSON.stringify(res.data));
        }
      } catch (err) {
        // Interceptor handles 401 redirect
      }
    };
    fetchUser();
    return () => { isMounted = false; };
  }, []);

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // Ignore network errors during logout
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      navigate('/login');
    }
  };

  const displayName = currentUser?.full_name || currentUser?.name || 'Examiner';
  const displayEmail = currentUser?.email || 'authenticated@sat-sa.local';
  const displayRole = (currentUser?.role || 'SUPERVISOR').toUpperCase();
  const initials = displayName
    .split(' ')
    .filter(Boolean)
    .map((n) => n[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'EX';

  const isSupervisor = displayRole === 'SUPERVISOR';

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-xl font-bold tracking-wider text-blue-400">SAT-SA</h1>
          <p className="text-xs text-slate-400 mt-1">Supervisory Analytics Tool</p>
        </div>
        
        <nav className="flex-1 overflow-y-auto py-4">
          <ul className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path || 
                              (item.path !== '/' && location.pathname.startsWith(item.path));
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center px-4 py-3 text-sm transition-colors ${
                      isActive 
                        ? 'bg-blue-900/50 text-blue-400 border-r-4 border-blue-400' 
                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                    }`}
                  >
                    <Icon className="w-5 h-5 mr-3" />
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        
        <div className="p-4 border-t border-slate-700 bg-slate-800/80">
          <div className="flex items-center mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center mr-3 font-semibold text-xs text-white shadow-sm ${
              isSupervisor ? 'bg-blue-600' : 'bg-emerald-600'
            }`}>
              <span>{initials}</span>
            </div>
            <div className="overflow-hidden min-w-0 flex-1">
              <p className="text-xs font-semibold text-slate-200 truncate">{displayName}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-medium tracking-wide uppercase ${
                  isSupervisor
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                }`}>
                  {displayRole}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate mt-0.5">{displayEmail}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="flex items-center text-xs font-medium text-slate-400 hover:text-red-300 transition-colors w-full pt-2 border-t border-slate-700/60 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5 mr-2" />
            Sign Out
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-slate-800 border-b border-slate-700 flex items-center px-6 justify-between shrink-0">
          <h2 className="text-lg font-medium text-slate-200">
            {navItems.find(item => location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path)))?.label || 'SAT-SA'}
          </h2>
          <div className="flex items-center space-x-4">
            <div className="bg-slate-700 px-3 py-1.5 rounded text-xs font-medium border border-slate-600">
              <span className="text-green-400 mr-2">●</span>
              SYSTEM ONLINE
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6 bg-slate-900">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
