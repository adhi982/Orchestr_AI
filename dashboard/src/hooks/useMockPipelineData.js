import { useEffect, useState } from 'react';

const initialData = {
  pipeline: {
    id: 'pipeline-1',
    status: 'running',
    progress: 0.75,
    duration: '34m 54s',
    lastRun: '7:01:59 PM',
  },
  agents: [
    { name: 'Lint Agent', status: 'success', duration: '45s' },
    { name: 'Test Agent', status: 'success', duration: '120s' },
    { name: 'Build Agent', status: 'success', duration: '180s' },
    { name: 'Security Agent', status: 'running', duration: null },
  ],
  logs: [
    { time: '7:36:47 PM', agent: 'Build Agent', message: 'Starting build process...' },
    { time: '7:36:42 PM', agent: 'Lint Agent', message: '✓ ESLint checks passed' },
    { time: '7:36:08 PM', agent: 'Lint Agent', message: '✓ Prettier formatting verified' },
    { time: '7:35:52 PM', agent: 'Test Agent', message: 'Running unit tests...' },
    { time: '7:35:28 PM', agent: 'Build Agent', message: '✓ Assets optimized' },
    { time: '7:35:02 PM', agent: 'Test Agent', message: '✓ Coverage: 87%' },
    { time: '7:34:47 PM', agent: 'Security Agent', message: 'Starting security scan...' },
    { time: '7:34:27 PM', agent: 'Lint Agent', message: '✓ TypeScript compilation successful' },
  ],
  notifications: [
    { type: 'success', title: 'Pipeline Completed', message: 'All agents completed successfully', time: '5m ago' },
    { type: 'info', title: 'Build Started', message: 'Pipeline #1234 started execution', time: '3m ago' },
    { type: 'warning', title: 'Test Coverage Low', message: 'Test coverage is below threshold', time: '2m ago' },
  ],
};

export default function useMockPipelineData() {
  const [data, setData] = useState(initialData);

  // Simulate real-time updates (for demo only)
  useEffect(() => {
    const interval = setInterval(() => {
      setData((prev) => ({
        ...prev,
        pipeline: {
          ...prev.pipeline,
          progress: prev.pipeline.progress < 1 ? prev.pipeline.progress + 0.01 : 1,
        },
      }));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return data;
} 