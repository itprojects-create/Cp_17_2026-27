import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, AlertTriangle } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-(--bg-primary) p-6">
      <div className="text-center max-w-md animate-fade-in">
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <AlertTriangle size={40} className="text-amber-400" />
          </div>
        </div>
        <h1 className="text-6xl font-black text-(--text-primary) tracking-tight mb-3">404</h1>
        <h2 className="text-xl font-semibold text-(--text-primary) mb-3">Page Not Found</h2>
        <p className="text-(--text-secondary) text-sm mb-8 leading-relaxed">
          The page you're looking for doesn't exist or has been moved. Double-check the URL or
          navigate back to the dashboard.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => navigate('/app/dashboard')}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-semibold hover:bg-primary-600 transition-all hover:scale-105"
          >
            <Home size={16} />
            Go to Dashboard
          </button>
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-(--border-default) text-(--text-primary) text-sm font-semibold hover:bg-(--bg-secondary) transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
};
