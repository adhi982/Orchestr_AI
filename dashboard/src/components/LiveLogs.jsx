import React, { useState, useRef, useEffect } from 'react';
import { usePipeline } from '../context/PipelineContext';

const LiveLogs = React.memo(function LiveLogs() {
  const { logs, agents } = usePipeline();
  const [selectedAgent, setSelectedAgent] = useState('All Agents');
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef(null);
  const logContainerRef = useRef(null);

  const filteredLogs = selectedAgent === 'All Agents'
    ? logs
    : logs.filter(log => log.agent === selectedAgent.replace(' Agent', '').toLowerCase());

  // Smart auto-scroll logic
  useEffect(() => {
    // Auto-scroll only the logs container, not the full page
    if (autoScroll && logContainerRef.current) {
      const logDiv = logContainerRef.current;
      logDiv.scrollTop = logDiv.scrollHeight;
    }
  }, [filteredLogs, autoScroll]);

  // Pause auto-scroll if user scrolls up in the log area
  useEffect(() => {
    const logDiv = logContainerRef.current;
    if (!logDiv) return;
    const handleScroll = () => {
      // If user is at the bottom, enable auto-scroll
      if (logDiv.scrollHeight - logDiv.scrollTop === logDiv.clientHeight) {
        setAutoScroll(true);
      } else {
        setAutoScroll(false);
      }
    };
    logDiv.addEventListener('scroll', handleScroll);
    return () => logDiv.removeEventListener('scroll', handleScroll);
  }, []);

  // Resume auto-scroll if user clicks outside the log area
  useEffect(() => {
    const handleClick = (e) => {
      if (logContainerRef.current && !logContainerRef.current.contains(e.target)) {
        setAutoScroll(true);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow flex flex-col gap-2">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-base font-semibold text-green-400 flex items-center gap-2">
          Live Logs
          <span className="bg-green-500 text-xs rounded-full px-2 py-0.5 ml-2">{filteredLogs.length}</span>
        </h3>
        <div className="flex items-center gap-2">
          <select
            className="bg-gray-700 text-gray-200 text-xs rounded px-2 py-1"
            value={selectedAgent}
            onChange={e => setSelectedAgent(e.target.value)}
          >
            <option>All Agents</option>
            {agents.map(a => (
              <option key={a.name}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>
      <div ref={logContainerRef} className="h-48 overflow-y-auto bg-gray-900 rounded p-2 text-sm">
        {filteredLogs.map((log, idx) => (
          <div key={idx} className="flex items-center gap-2 mb-1">
            <span className="text-xs text-gray-500 w-20">{log.time}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">{log.agent}</span>
            <span className="text-gray-200">{log.message}</span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  );
});

export default LiveLogs; 