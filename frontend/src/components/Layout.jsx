import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, Upload, Search, Activity, FileText, 
  AlertTriangle, Eye, Users, FileBarChart, LogOut 
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/upload', label: 'Upload Data', icon: Upload },
  { path: '/findings', label: 'Supervisory Findings', icon: AlertTriangle },
  { path: '/review-queue', label: 'Review Queue', icon: Eye },
  { path: '/benchmarks', label: 'Peer Benchmarking', icon: Users },
  { path: '/reports', label: 'Reports', icon: FileBarChart },
];

const Layout = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

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
        
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center mb-4">
            <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center mr-3">
              <span className="text-sm font-medium">SU</span>
            </div>
            <div>
              <p className="text-sm font-medium">Supervisor</p>
              <p className="text-xs text-slate-400">admin@ntro.gov</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="flex items-center text-sm text-slate-400 hover:text-white transition-colors w-full"
          >
            <LogOut className="w-4 h-4 mr-2" />
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
