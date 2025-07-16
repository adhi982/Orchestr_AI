import React from 'react';
import { usePipeline } from '../context/PipelineContext';
import PipelineSelector from './PipelineSelector';

function formatDateTime(ts) {
  if (!ts) return 'N/A';
  const d = new Date(ts);
  const date = d.toLocaleDateString();
  const time = d.toLocaleTimeString();
  return `${date}, ${time}`;
}

export default function PipelineStatus() {
  const { pipeline, loading, error, selectedId, setSelectedId, pipelines } = usePipeline();

  const isActive = pipeline && (pipeline.status === 'pending' || pipeline.status === 'in_progress');
  const isSuccess = pipeline && pipeline.status === 'success';
  const progress = pipeline && typeof pipeline.progress === 'number' ? pipeline.progress : 0;

  return (
    <div className="bg-gray-800 rounded-lg p-6 flex flex-col gap-4 shadow relative">
      {/* Overlay spinner when loading */}
      {loading && (
        <div className="absolute inset-0 bg-gray-900 bg-opacity-60 flex items-center justify-center z-10 rounded-lg">
          <svg className="animate-spin h-8 w-8 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l5-5-5-5v4a10 10 0 00-10 10h4z"></path>
          </svg>
        </div>
      )}
      {/* Inline error message */}
      {error && (
        <div className="absolute inset-0 bg-gray-900 bg-opacity-80 flex items-center justify-center z-20 rounded-lg">
          <span className="text-red-400 font-semibold">Error: {error}</span>
        </div>
      )}
      <div className="flex flex-row justify-between items-start mb-2">
        <div>
          <h2 className="text-3xl font-extrabold text-blue-400 flex items-center gap-2 tracking-tight">
            <span className="inline-block w-3 h-3 bg-blue-400 rounded-full animate-pulse"></span>
            Pipeline Status:
            <span className="ml-2 text-white capitalize">{pipeline?.status || 'N/A'}</span>
          </h2>
          <div className="text-xs text-gray-400 mt-1">Created: <span className="text-white">{formatDateTime(pipeline?.start_time)}</span></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex flex-col items-end">
            <span className="text-xs text-gray-400 mb-1">Select Pipeline ID</span>
            <div className="flex items-center gap-2">
              {/* Spinning refresh icon only when active */}
              <span className="inline-block">
                <svg className={`${isActive ? 'animate-spin' : ''} h-6 w-6 text-blue-400`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l5-5-5-5v4a10 10 0 00-10 10h4z"></path>
                </svg>
              </span>
              <select
                className="bg-gray-700 text-gray-200 text-xs rounded px-2 py-1"
                value={selectedId}
                onChange={e => setSelectedId(e.target.value)}
              >
                {pipelines.map(p => (
                  <option key={p.id} value={p.id}>{p.id} ({p.status})</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </div>
      {/* Animated Progress Bar */}
      <div className="w-full h-4 bg-gray-700 rounded-full overflow-hidden relative mt-2 shadow-inner">
        {/* Modern gradient fill */}
        <div
          className={`h-full transition-all duration-500 ${isSuccess ? 'bg-gradient-to-r from-green-400 to-blue-500 shadow-lg' : 'bg-gradient-to-r from-blue-400 via-blue-500 to-blue-600'}`}
          style={{ width: `${progress}%` }}
        ></div>
        {/* Simple animated running bar if active */}
        {isActive && (
          <div className="absolute top-0 left-0 h-full w-full pointer-events-none">
            <div className="animate-running-bar" />
          </div>
        )}
        {/* Subtle glow/checkmark if success */}
        {isSuccess && (
          <div className="absolute inset-0 flex items-center justify-end pr-2">
            <svg className="h-5 w-5 text-green-300 drop-shadow-lg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
        )}
      </div>
    </div>
  );
}

/* Add to your global CSS (e.g., index.css):
.animate-running-bar {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  width: 20%;
  background: rgba(255,255,255,0.20);
  border-radius: 9999px;
  animation: running-bar-loop 1.2s linear infinite;
}
@keyframes running-bar-loop {
  0% { left: -20%; }
  100% { left: 100%; }
}
*/ 