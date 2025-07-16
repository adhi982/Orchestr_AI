import React, { useState } from 'react';
import { usePipeline } from '../context/PipelineContext';

const statusStyles = {
  success: 'border-2 border-green-400 bg-gray-900 shadow-sm',
  running: 'border-2 border-blue-400 bg-gray-900 shadow-sm',
  failed: 'border-2 border-red-400 bg-gray-900 shadow-sm',
  pending: 'border-2 border-gray-700 bg-gray-900 shadow-sm',
};

const statusText = {
  success: 'text-green-400',
  running: 'text-blue-400',
  failed: 'text-red-400',
  pending: 'text-gray-400',
};

const statusIcon = {
  success: (
    <svg className="w-5 h-5 text-green-400 absolute top-2 right-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
  ),
  running: (
    <svg className="w-5 h-5 text-blue-400 absolute top-2 right-2 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path d="M12 2a10 10 0 0110 10" stroke="currentColor" strokeWidth="4" /></svg>
  ),
  failed: (
    <svg className="w-5 h-5 text-red-400 absolute top-2 right-2" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
  ),
  pending: null,
};

// Simple Markdown parser for headings, bullets, and paragraphs
function renderMarkdown(text) {
  if (!text) return null;
  const lines = text.split(/\r?\n/);
  const elements = [];
  let currentList = null;
  lines.forEach((line, idx) => {
    if (/^##+ /.test(line)) {
      // Heading
      const level = line.match(/^#+/)[0].length;
      const content = line.replace(/^#+ /, '');
      elements.push(
        <div key={`h${idx}`} className={`font-bold mt-3 mb-1 ${level === 2 ? 'text-base' : 'text-sm'}`}>{content}</div>
      );
      currentList = null;
    } else if (/^\s*[-*] /.test(line)) {
      // Bullet point
      if (!currentList) {
        currentList = [];
        elements.push(<ul key={`ul${idx}`} className="list-disc ml-5 mb-1">{currentList}</ul>);
      }
      currentList.push(
        <li key={`li${idx}`} className="mb-1">{line.replace(/^\s*[-*] /, '')}</li>
      );
    } else if (line.trim() === '') {
      // Blank line, end list
      currentList = null;
    } else {
      // Paragraph
      elements.push(
        <div key={`p${idx}`} className="mb-1 text-gray-300">{line}</div>
      );
      currentList = null;
    }
  });
  return elements;
}

export default function PipelineFlow() {
  const { agents, geminiSuggestions, lintMlSuggestions, lintMlIssues } = usePipeline();
  const [showSecuritySuggestions, setShowSecuritySuggestions] = useState(false);
  const [showLintSuggestions, setShowLintSuggestions] = useState(false);

  // Extract Gemini suggestion text if in Gemini API format
  let suggestionText = '';
  if (geminiSuggestions) {
    if (typeof geminiSuggestions === 'string') {
      suggestionText = geminiSuggestions;
    } else if (
      geminiSuggestions.candidates &&
      geminiSuggestions.candidates[0] &&
      geminiSuggestions.candidates[0].content &&
      geminiSuggestions.candidates[0].content.parts &&
      geminiSuggestions.candidates[0].content.parts[0] &&
      geminiSuggestions.candidates[0].content.parts[0].text
    ) {
      suggestionText = geminiSuggestions.candidates[0].content.parts[0].text;
    }
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 flex flex-col gap-6 shadow">
      <h3 className="text-xl font-bold text-white mb-4 tracking-tight">Pipeline Flow</h3>
      <div className="flex items-end justify-between gap-4">
        {agents.map((agent, idx) => (
          <React.Fragment key={agent.name}>
            <div className={`relative flex flex-col items-center w-40 h-32 rounded-xl transition-all duration-300 ${statusStyles[agent.status]}`}
              style={{ boxShadow: agent.status === 'running' ? '0 0 0 2px #60a5fa' : undefined }}>
              {/* Status Icon */}
              {statusIcon[agent.status]}
              {/* Agent Name */}
              <span className="mt-8 text-base font-bold text-white text-center">{agent.name}</span>
              {/* Status */}
              <span className={`mt-1 text-xs font-medium ${statusText[agent.status]}`}>{agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}</span>
              {/* Duration for all agents (replace with iteration info for card) */}
              <span className="mt-1 text-xs font-semibold text-gray-300">
                {agent.status === 'success' ? (
                  <span className="flex items-center gap-1">
                    {`${agent.retries + 1}/${typeof agent.maxRetries === 'number' ? agent.maxRetries + 1 : agent.retries + 1}`}
                    <span title="Iteration in which agent succeeded / max allowed attempts" className="ml-1 cursor-pointer">
                      <svg xmlns="http://www.w3.org/2000/svg" className="inline w-3 h-3 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" fill="none"/><text x="12" y="16" textAnchor="middle" fontSize="12" fill="#60a5fa" fontFamily="Arial">i</text></svg>
                    </span>
                  </span>
                ) : ''}
              </span>
            </div>
            {idx < agents.length - 1 && (
              <div className="flex-1 h-1 bg-gray-700 mx-2 rounded-full relative flex items-center justify-center">
                <span className="w-2 h-2 bg-gray-800 border-2 border-gray-700 rounded-full"></span>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
      {/* Bottom row: agent names and durations, and suggestions button for Security Agent */}
      <div className="flex justify-between mt-6 px-2">
        {agents.map(agent => (
          <div key={agent.name} className="flex flex-col items-center w-40">
            <span className="text-xs text-gray-400 font-medium">{agent.name}</span>
            <span className="text-base font-bold text-white mt-1">{agent.duration}</span>
            {agent.name === 'Lint Agent' && (
              <>
                <button
                  className="mt-2 px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition"
                  onClick={() => setShowLintSuggestions(v => !v)}
                >
                  Realtime Suggestions
                </button>
                {showLintSuggestions && (
                  <div className="absolute z-50 top-28 left-1/2 -translate-x-1/2 w-[700px] h-[600px] bg-gray-900 border border-blue-400 rounded shadow-lg p-6 text-base text-gray-100 max-h-[600px] overflow-y-auto font-sans leading-relaxed" style={{fontFamily: 'Inter, Segoe UI, Arial, sans-serif', letterSpacing: '0.01em'}}>
                    <div className="flex justify-between items-center mb-2">
                      <div className="font-bold text-xl">Lint Agent Integrated ML Suggestions</div>
                      <button onClick={() => setShowLintSuggestions(false)} className="text-gray-400 hover:text-red-400 text-2xl font-bold focus:outline-none" aria-label="Close">
                        &times;
                      </button>
                    </div>
                    {lintMlIssues && lintMlIssues.length > 0 ? (
                      lintMlIssues.map((issue, idx) => (
                        <div key={idx} className="mb-4 border-b border-gray-700 pb-2">
                          <div className="font-bold text-blue-300 text-lg">{issue.type} <span className="text-xs text-gray-400">({issue.severity})</span></div>
                          <div className="text-xs text-gray-400 mb-1">
                            {issue.file_path} (line {issue.line_number})
                          </div>
                          <div className="mb-1 text-gray-200">{issue.suggestion ? issue.suggestion : <span className="text-gray-400">No suggestion available.</span>}</div>
                        </div>
                      ))
                    ) : (
                      lintMlSuggestions && lintMlSuggestions.no_issues_explanation && agents.find(a => a.name === 'Lint Agent').status === 'success' ? (
                        <>
                          <div className="text-green-400 font-bold mb-4 text-2xl">Issues found: 0</div>
                          <div className="text-green-300 text-xl">{renderMarkdown(lintMlSuggestions.no_issues_explanation)}</div>
                        </>
                      ) : (
                        agents.find(a => a.name === 'Lint Agent').status === 'success' ? (
                          <div className="text-green-400 font-semibold text-xl">No issues found in the analyzed files!</div>
                        ) : null
                      )
                    )}
                  </div>
                )}
              </>
            )}
            {agent.name === 'Security Agent' && (
              <>
                <button
                  className="mt-2 px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition"
                  onClick={() => setShowSecuritySuggestions(v => !v)}
                >
                  Realtime Suggestions
                </button>
                {showSecuritySuggestions && (
                  <div className="absolute z-50 top-28 left-1/2 -translate-x-1/2 w-[700px] h-[600px] bg-gray-900 border border-blue-400 rounded shadow-lg p-6 text-base text-gray-100 max-h-[600px] overflow-y-auto font-sans leading-relaxed" style={{fontFamily: 'Inter, Segoe UI, Arial, sans-serif', letterSpacing: '0.01em'}}>
                    <div className="flex justify-between items-center mb-2">
                      <div className="font-bold text-xl">Security Agent Personalized Suggestions</div>
                      <button onClick={() => setShowSecuritySuggestions(false)} className="text-gray-400 hover:text-red-400 text-2xl font-bold focus:outline-none" aria-label="Close">
                        &times;
                      </button>
                    </div>
                    {suggestionText ? (
                      <div>{renderMarkdown(suggestionText)}</div>
                    ) : (
                      <div className="text-gray-400">No suggestions available.</div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
} 