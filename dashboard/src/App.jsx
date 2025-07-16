import React from 'react';
import { PipelineProvider } from './context/PipelineContext';
import Header from './components/Header';
import PipelineStatus from './components/PipelineStatus';
import PipelineFlow from './components/PipelineFlow';
import AgentPanel from './components/AgentPanel';
import LiveLogs from './components/LiveLogs';

export default function App() {
  return (
    <PipelineProvider>
      <div className="min-h-screen bg-gray-900 text-white flex flex-col">
        <Header />
        <main className="flex-1 flex flex-col md:flex-row gap-4 p-6">
          <section className="flex-1 flex flex-col gap-4">
            <PipelineStatus />
            <PipelineFlow />
            <LiveLogs />
          </section>
          <aside className="w-full md:w-96 flex flex-col gap-4">
            <AgentPanel />
          </aside>
        </main>
      </div>
    </PipelineProvider>
  );
} 