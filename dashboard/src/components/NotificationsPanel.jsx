import React from 'react';
import { usePipeline } from '../context/PipelineContext';

const typeColors = {
  success: 'bg-green-500',
  info: 'bg-blue-500',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
};

export default function NotificationsPanel() {
  const { notifications } = usePipeline();
  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow flex flex-col gap-2">
      <h3 className="text-base font-semibold text-gray-200 mb-2">Notifications</h3>
      <div className="flex flex-col gap-2">
        {notifications.map((n, idx) => (
          <div key={idx} className="flex items-center gap-3 p-2 rounded-lg bg-gray-900">
            <span className={`w-2 h-2 rounded-full ${typeColors[n.type]}`}></span>
            <div className="flex-1">
              <div className="text-xs font-bold text-gray-100">{n.title} <span className="ml-2 text-gray-400 font-normal">{n.type}</span></div>
              <div className="text-xs text-gray-300">{n.message}</div>
            </div>
            <span className="text-xs text-gray-400">{n.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
} 