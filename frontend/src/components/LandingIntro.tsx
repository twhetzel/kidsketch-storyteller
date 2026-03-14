"use client";

import React from "react";
import { Camera } from "lucide-react";

interface LandingIntroProps {
  onReady: () => void;
}

export const LandingIntro: React.FC<LandingIntroProps> = ({ onReady }) => {
  return (
    <div className="w-full flex flex-col items-center space-y-8 p-6 md:p-8 bg-white rounded-3xl shadow-2xl border border-gray-300 min-h-[420px] animate-fade-in-up">
      <h1 className="text-3xl font-black text-purple-600 font-comic text-center">
        KidSketch Storyteller 🎨
      </h1>
      <p className="text-gray-700 text-center text-lg leading-relaxed">
        Draw a character and we&apos;ll turn them into
        <br />
        the hero of your movie.
      </p>
      <div className="w-full text-left">
        <h2 className="text-lg font-bold text-gray-800 font-comic mb-3">How it works</h2>
        <ol className="text-gray-700 space-y-2 list-decimal list-inside font-medium">
          <li>Draw a character (on paper or a tablet).</li>
          <li>Hold your drawing in front of the camera.</li>
          <li>We bring them to life and you create the story together.</li>
        </ol>
      </div>
      <button
        onClick={onReady}
        className="w-full flex items-center justify-center gap-2 bg-sky-500 hover:bg-sky-600 text-white py-4 px-6 rounded-xl font-bold text-lg shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
      >
        <Camera size={24} />
        Let&apos;s get started
      </button>
    </div>
  );
};
