import React from 'react';

export default function DarkModeToggle() {
  return (
    <button
      className="w-10 h-6 flex items-center bg-gray-700 rounded-full p-1 focus:outline-none"
      title="Toggle dark mode"
    >
      <span className="w-4 h-4 bg-white rounded-full shadow transform transition-transform" style={{ transform: 'translateX(0)' }}></span>
    </button>
  );
} 