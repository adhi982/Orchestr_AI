import React from 'react';
import { usePipeline } from '../context/PipelineContext';


// Helper to render bullet points from holistic Gemini JSON
function renderHolisticSuggestions(suggestions) {
  if (!suggestions) return <div className="text-gray-400">No suggestions available.</div>;
  // Show error if present
  if (suggestions.error) {
    return <div className="text-red-400">Gemini Error: {suggestions.error}</div>;
  }
  // Try to extract the main text from Gemini API response
  let parsed = suggestions;
  if (suggestions.candidates && suggestions.candidates[0] && suggestions.candidates[0].content && suggestions.candidates[0].content.parts && suggestions.candidates[0].content.parts[0] && suggestions.candidates[0].content.parts[0].text) {
    try {
      parsed = JSON.parse(suggestions.candidates[0].content.parts[0].text);
    } catch {
      // fallback to raw text
      return <div className="text-gray-400">{suggestions.candidates[0].content.parts[0].text}</div>;
    }
  }
  // If parsed is a string, show as is
  if (typeof parsed === 'string') {
    return <div className="text-gray-400">{parsed}</div>;
  }
  // Render each key as a bullet point
  return (
    <ul className="list-disc ml-5 space-y-2 text-sm text-gray-200">
      {Object.entries(parsed).map(([key, value]) => (
        <li key={key}><span className="font-semibold capitalize">{key}:</span> {value}</li>
      ))}
    </ul>
  );
}

export default function AgentPanel() {
  const { aiSummary, aiSummaryLoading, aiSummaryError, triggerAiSummary, selectedId } = usePipeline();
  return (
    <div className="bg-gray-800 rounded-lg p-6 shadow flex flex-col gap-2">
      <h3 className="text-base font-semibold text-gray-200 mb-2">Agentic DevOps Summary</h3>
      {selectedId && (
        <button
          className="mb-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded shadow w-max"
          onClick={triggerAiSummary}
          disabled={aiSummaryLoading}
        >
          {aiSummaryLoading ? 'Loading AI Summary...' : 'Get AI Summary'}
        </button>
      )}
      {aiSummaryError && <div className="text-red-400">AI Error: {aiSummaryError}</div>}
      {aiSummary && Array.isArray(aiSummary) && (
        <ul className="list-disc ml-5 space-y-2 text-sm text-gray-200">
          {aiSummary.map((point, idx) => (
            <li key={idx}>{point}</li>
          ))}
        </ul>
      )}
      {!aiSummary && !aiSummaryLoading && !aiSummaryError && (
        <div className="text-gray-400">No AI summary yet. Click the button above to generate one.</div>
      )}
    </div>
  );
} 