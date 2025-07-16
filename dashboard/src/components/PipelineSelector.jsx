import React from 'react';
import usePipelineList from '../hooks/usePipelineList';

export default function PipelineSelector({ selectedId, onSelect }) {
  const { pipelines, loading, error } = usePipelineList();

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm text-gray-400 font-medium">Select Pipeline ID</span>
      {loading ? (
        <select className="bg-gray-700 text-gray-400 rounded px-2 py-1" disabled>
          <option>Loading...</option>
        </select>
      ) : error ? (
        <select className="bg-gray-700 text-red-400 rounded px-2 py-1" disabled>
          <option>Error loading pipelines</option>
        </select>
      ) : (
        <select
          className="bg-gray-700 text-white rounded px-2 py-1"
          value={selectedId || ''}
          onChange={e => onSelect(e.target.value)}
        >
          <option value="" disabled>Select a pipeline</option>
          {pipelines.map(p => (
            <option key={p.id} value={p.id}>
              {p.id} ({p.status})
            </option>
          ))}
        </select>
      )}
    </div>
  );
} 