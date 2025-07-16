import React, { createContext, useContext, useState, useEffect } from 'react';
import usePipelineData from '../hooks/usePipelineData';
import usePipelineList from '../hooks/usePipelineList';

const PipelineContext = createContext();

// Store last known non-'N/A' durations for each agent
const lastDurations = {};

function formatDuration(seconds) {
  if (!seconds || isNaN(seconds)) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDurationShort(seconds) {
  if (!seconds || isNaN(seconds)) return 'N/A';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return s === 0 ? `${m}min` : `${m}min ${s}s`;
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${h}h ${min}min${s ? ` ${s}s` : ''}`;
}

function formatTimestamp(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleString();
}

function mapBackendToUI(data) {
  if (!data) return { pipeline: {}, agents: [], logs: [], notifications: [], geminiSuggestions: null, holisticGeminiSuggestions: null, lintMlSuggestions: null };
  // Determine start_time: prefer data.start_time, else use first stage timestamp
  let start_time = data.start_time;
  if (!start_time && data.stages) {
    const firstStage = Object.values(data.stages)[0];
    if (firstStage && firstStage.timestamp) {
      start_time = firstStage.timestamp;
    }
  }
  // Map pipeline
  const pipeline = {
    id: data.pipeline_id,
    status: data.status,
    progress: typeof data.progress === 'number' ? data.progress : 0,
    duration: formatDuration(data.duration),
    lastRun: formatTimestamp(data.end_time),
    start_time: start_time || '',
  };
  // Only include real agent stages
  const agentStageNames = ['lint', 'test', 'build', 'security'];
  // Map of max retries per agent from pipeline.yml (retries + 1 = max attempts)
  const maxRetriesMap = { lint: 2, test: 1, build: 1, security: 2 };
  const agents = Object.entries(data.stages || {})
    .filter(([name]) => agentStageNames.includes(name))
    .map(([name, stage]) => {
      let duration = 'N/A';
      // Prefer per-stage start_time and end_time if available
      if (stage.start_time && stage.end_time) {
        const start = new Date(stage.start_time).getTime();
        const end = new Date(stage.end_time).getTime();
        if (!isNaN(start) && !isNaN(end) && end > start) {
          let seconds = Math.round((end - start) / 1000);
          if (name === 'lint' && seconds < 1) {
            duration = '1s';
          } else {
            duration = formatDurationShort(seconds);
          }
        } else if (name === 'lint') {
          duration = '1s';
        }
      } else if (stage.status === 'success' && start_time && stage.timestamp) {
        // Fallback to previous logic
        const start = new Date(start_time).getTime();
        const end = new Date(stage.timestamp).getTime();
        if (!isNaN(start) && !isNaN(end) && end > start) {
          let seconds = Math.round((end - start) / 1000);
          if (name === 'lint' && seconds < 1) {
            duration = '1s';
          } else {
            duration = formatDurationShort(seconds);
          }
        } else if (name === 'lint') {
          duration = '1s';
        }
      } else if (name === 'lint') {
        duration = '1s';
      }
      // Persist last known non-'N/A' duration
      if (duration !== 'N/A') {
        lastDurations[name] = duration;
      } else if (lastDurations[name]) {
        duration = lastDurations[name];
      }
      return {
        name: name.charAt(0).toUpperCase() + name.slice(1) + ' Agent',
        status: stage.status || 'pending',
        duration,
        retries: typeof stage.retries === 'number' ? stage.retries : 0,
        maxRetries: typeof maxRetriesMap[name] === 'number' ? maxRetriesMap[name] : 0,
      };
    });
  // Map logs and notifications from backend data
  const logs = Array.isArray(data.logs) ? data.logs : [];
  const notifications = Array.isArray(data.notifications) ? data.notifications : [];
  // Extract Gemini suggestions for Security Agent if present
  let geminiSuggestions = null;
  if (data.stages && data.stages.security && data.stages.security.results && data.stages.security.results.gemini_suggestions) {
    geminiSuggestions = data.stages.security.results.gemini_suggestions;
  }
  // Extract ML suggestions for Lint Agent if present
  let lintMlSuggestions = null;
  let lintMlIssues = [];
  if (data.stages && data.stages.lint && data.stages.lint.results) {
    if (data.stages.lint.results.ml_suggestions) {
      lintMlSuggestions = data.stages.lint.results.ml_suggestions;
    }
    if (data.stages.lint.results.issues) {
      lintMlIssues = data.stages.lint.results.issues;
    }
    // Extract no issues explanation if present
    if (data.stages.lint.results.no_issues_explanation) {
      lintMlSuggestions = lintMlSuggestions || {};
      lintMlSuggestions.no_issues_explanation = data.stages.lint.results.no_issues_explanation;
    }
  }
  // Expose holistic Gemini suggestions if present
  let holisticGeminiSuggestions = null;
  if (data.holistic_gemini_suggestions) {
    holisticGeminiSuggestions = data.holistic_gemini_suggestions;
  }
  return { pipeline, agents, logs, notifications, geminiSuggestions, holisticGeminiSuggestions, lintMlSuggestions, lintMlIssues };
}

export const PipelineProvider = ({ children }) => {
  const { pipelines } = usePipelineList();
  const [selectedId, setSelectedId] = useState('');

  // Always select the most recent pipeline (last in the list) by default
  useEffect(() => {
    if (pipelines.length > 0) {
      const latest = pipelines[pipelines.length - 1].id;
      if (selectedId !== latest) {
        setSelectedId(latest);
      }
    }
  }, [pipelines]);

  const { data, loading, error } = usePipelineData(selectedId);
  const mapped = mapBackendToUI(data);

  // --- AI summary state and trigger ---
  const [aiSummary, setAiSummary] = useState(null);
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false);
  const [aiSummaryError, setAiSummaryError] = useState(null);

  // Clear AI summary when pipeline changes
  useEffect(() => {
    setAiSummary(null);
    setAiSummaryError(null);
    setAiSummaryLoading(false);
  }, [selectedId]);

  const triggerAiSummary = async () => {
    if (!selectedId) return;
    setAiSummaryLoading(true);
    setAiSummaryError(null);
    setAiSummary(null);
    try {
      const res = await fetch(`http://localhost:8000/pipeline/${selectedId}/ai-summary`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setAiSummary(json.ai_summary || null);
    } catch (err) {
      setAiSummaryError(err.message);
    } finally {
      setAiSummaryLoading(false);
    }
  };

  return (
    <PipelineContext.Provider value={{ ...mapped, loading, error, selectedId, setSelectedId, pipelines, aiSummary, aiSummaryLoading, aiSummaryError, triggerAiSummary }}>
      {children}
    </PipelineContext.Provider>
  );
};

export const usePipeline = () => useContext(PipelineContext); 