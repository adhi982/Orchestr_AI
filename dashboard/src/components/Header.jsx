import React, { useState, useEffect } from 'react';
import DarkModeToggle from './DarkModeToggle';
import { usePipeline } from '../context/PipelineContext';

// Placeholder: Replace with real Docker status from backend or context
const dockerStatus = 'connected'; // 'connected', 'connecting', 'disconnected'

function getDockerIconColor(status) {
  if (status === 'connected') return 'text-green-400 drop-shadow-lg';
  if (status === 'disconnected') return 'text-red-400 opacity-60';
  return 'text-yellow-300 animate-pulse'; // connecting
}

export default function Header() {
  const [dockerStatus, setDockerStatus] = useState('connecting');
  const { notifications } = usePipeline();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = React.useRef(null);

  useEffect(() => {
    let interval = setInterval(async () => {
      try {
        const res = await fetch('http://localhost:8000/docker/status');
        const json = await res.json();
        setDockerStatus(json.status); // 'connected', 'disconnected'
      } catch {
        setDockerStatus('disconnected');
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    }
    if (showDropdown) {
      document.addEventListener('mousedown', handleClick);
    } else {
      document.removeEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showDropdown]);

  return (
    <header className="flex items-center justify-between px-6 py-4 bg-gray-800 rounded-b-lg shadow relative">
      <div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">DevOps Pipeline</h1>
        <p className="text-base text-gray-400 font-medium mt-1">Multi-Agent Orchestrator Dashboard</p>
      </div>
      <div className="flex items-center gap-6">
        {/* Notification Bell Icon */}
        <div className="relative" ref={dropdownRef}>
          <button
            className="relative focus:outline-none"
            onClick={() => setShowDropdown(v => !v)}
            aria-label="Show notifications"
          >
            <svg className="w-7 h-7 text-gray-300 hover:text-blue-400 transition" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            {notifications.length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 border-2 border-gray-800">{notifications.length}</span>
            )}
          </button>
          {/* Dropdown */}
          {showDropdown && (
            <div className="absolute right-0 mt-3 w-96 max-h-96 bg-gray-800 border border-blue-400 rounded-lg shadow-lg p-4 z-50 overflow-y-auto animate-fade-in">
              <h3 className="text-base font-semibold text-gray-200 mb-2">Notifications</h3>
              <div className="flex flex-col gap-2">
                {notifications.length === 0 ? (
                  <div className="text-gray-400 text-sm">No notifications</div>
                ) : notifications.map((n, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-2 rounded-lg bg-gray-900">
                    <span className={`w-2 h-2 rounded-full ${n.type === 'success' ? 'bg-green-500' : n.type === 'info' ? 'bg-blue-500' : n.type === 'warning' ? 'bg-yellow-500' : 'bg-red-500'}`}></span>
                    <div className="flex-1">
                      <div className="text-xs font-bold text-gray-100">{n.title} <span className="ml-2 text-gray-400 font-normal">{n.type}</span></div>
                      <div className="text-xs text-gray-300">{n.message}</div>
                    </div>
                    <span className="text-xs text-gray-400">{n.time}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        {/* Docker label and WiFi status icon */}
        <span className="flex items-center gap-2">
          <span className="uppercase font-bold text-gray-300 tracking-wider text-sm">Docker</span>
          <span className={`relative flex items-center justify-center ${getDockerIconColor(dockerStatus)}`} title="Docker Status">
            <svg
              className={`h-7 w-7 ${dockerStatus === 'connecting' ? 'animate-pulse' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              {/* WiFi/Network arcs */}
              <path d="M4.93 12.93a10 10 0 0114.14 0" strokeLinecap="round" />
              <path d="M8.46 16.46a5 5 0 017.07 0" strokeLinecap="round" />
              <circle cx="12" cy="20" r="1.5" fill="currentColor" />
            </svg>
          </span>
        </span>
      </div>
    </header>
  );
} 