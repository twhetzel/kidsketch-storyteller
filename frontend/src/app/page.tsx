"use client";

import React, { useState, useRef } from 'react';
import { WebcamCapture } from '@/components/WebcamCapture';
import { StoryCanvas } from '@/components/StoryCanvas';
import { AnimatedCharacter } from '@/components/AnimatedCharacter';
import { GeminiLiveMic } from '@/components/GeminiLiveMic';
import { Loader2 } from 'lucide-react';

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [characterName, setCharacterName] = useState("Your Friend");
  const [characterModel, setCharacterModel] = useState<any>(null);
  const [isTalking, setIsTalking] = useState(false);
  const [beats, setBeats] = useState<any[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [movieUrl, setMovieUrl] = useState<string | null>(null);
  const loadingRef = useRef<HTMLDivElement>(null);

  const handleExport = async () => {
    if (!sessionId) return;
    setIsExporting(true);
    setMovieUrl(null);
    try {
      const res = await fetch(`http://localhost:8000/session/${sessionId}/export`);
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Export failed: ${res.status}`);
      }
      const data = await res.json();
      setMovieUrl(data.movieUrl);
    } catch (error: any) {
      console.error("Export failed:", error);
      alert(`Oops! Making the movie failed: ${error.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  // Called when the mic button is clicked to stop — generate a new beat from what was said
  const handleMicStop = (transcript: string) => {
    console.log("🎙️ Mic stopped. Transcript:", transcript);
    setIsTalking(true);
    setTimeout(() => setIsTalking(false), 4000);
    if (sessionId && !isGenerating) {
      console.log("🎬 Generating new scene from voice:", transcript);
      generateBeat(sessionId, transcript);
      setTimeout(() => loadingRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 100);
    }
  };

  const handleCapture = async (imageSrc: string) => {
    setIsAnalyzing(true);
    try {
      // 1. Initialize Session
      const initRes = await fetch('http://localhost:8000/session/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sketch_url: "pending" })
      });

      if (!initRes.ok) {
        throw new Error(`Init failed: ${initRes.status}`);
      }

      const { sessionId } = await initRes.json();
      if (!sessionId) throw new Error("No sessionId returned");
      setSessionId(sessionId);

      // 2. Upload and Analyze
      const blob = await (await fetch(imageSrc)).blob();
      const analyzeRes = await fetch(`http://localhost:8000/session/${sessionId}/analyze`, {
        method: 'POST',
        body: blob,
      });

      if (!analyzeRes.ok) {
        throw new Error(`Analyze failed: ${analyzeRes.status}`);
      }

      const data = await analyzeRes.json();
      const { profile, model } = data;
      setCharacterName(profile.name || "A New Friend");
      setCharacterModel(model);

      // 3. Kick off first beat automatically
      generateBeat(sessionId);
    } catch (error) {
      console.error("Failed to start story:", error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const generateBeat = async (sid: string, instruction?: string) => {
    setIsGenerating(true);
    try {
      const url = instruction
        ? `http://localhost:8000/session/${sid}/beat?user_instruction=${encodeURIComponent(instruction)}`
        : `http://localhost:8000/session/${sid}/beat`;

      const beatRes = await fetch(url, { method: 'POST' });
      if (!beatRes.ok) {
        throw new Error(`Beat failed: ${beatRes.status}`);
      }
      const beat = await beatRes.json();
      if (beat && beat.id) {
        setBeats(prev => [...prev, beat]);
      }
    } catch (error) {
      console.error("Failed to generate beat:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4 md:p-8 bg-[#fff9f0]">
      {!sessionId ? (
        <div className="w-full max-w-md animate-fade-in-up">
          {isAnalyzing ? (
            <div className="flex flex-col items-center space-y-6 p-12 bg-white rounded-3xl shadow-2xl border-4 border-purple-100">
              <Loader2 className="w-16 h-16 text-purple-500 animate-spin" />
              <h2 className="text-2xl font-bold text-gray-700 font-comic">Looking at your drawing... ✨</h2>
              <p className="text-gray-400 text-center italic">"I think I see a hero in there!"</p>
            </div>
          ) : (
            <WebcamCapture onCapture={handleCapture} />
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center space-y-8 w-full">
          {characterModel && (
            <div className="w-full max-w-sm">
              <AnimatedCharacter
                imageUrl={characterModel.imageUrl}
                name={characterName}
                isTalking={isTalking}
              />
            </div>
          )}

          <StoryCanvas
            beats={beats}
            characterName={characterName}
            isGenerating={isGenerating}
            onNext={() => sessionId && generateBeat(sessionId)}
            loadingRef={loadingRef}
          />
          <GeminiLiveMic
            sessionId={sessionId}
            onStop={handleMicStop}
          />

          <div className="flex flex-col items-center space-y-4 pt-8">
            <button
              onClick={handleExport}
              disabled={isExporting || beats.length === 0}
              className="bg-green-500 hover:bg-green-600 disabled:bg-gray-300 text-white px-10 py-4 rounded-full font-black text-xl shadow-2xl transition-all hover:scale-105 active:scale-95"
            >
              {isExporting ? '🎬 Making your movie...' : '📽️ Export My Movie!'}
            </button>

            {movieUrl && (
              <a
                href={movieUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 font-bold underline animate-bounce"
              >
                Click here to see your movie! 🍿
              </a>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
