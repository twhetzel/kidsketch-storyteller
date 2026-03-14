"use client";

import React, { useState, useRef, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { WebcamCapture } from '@/components/WebcamCapture';
import { LandingIntro } from '@/components/LandingIntro';
import { StoryCanvas } from '@/components/StoryCanvas';
import { AnimatedCharacter } from '@/components/AnimatedCharacter';
import { GeminiLiveMic } from '@/components/GeminiLiveMic';
import { Loader2, Paintbrush, Sparkles, X } from 'lucide-react';

interface CharacterProfile {
  name: string;
  description: string;
  visualTraits: string[];
}

interface CharacterModel {
  imageUrl: string;
  traits: string[];
  basePrompt: string;
}

interface StoryBeat {
  id: string;
  sceneTitle: string;
  narration: string;
  audioUrl: string;
  imagePrompt: string;
  imageUrl: string;
  timestamp: number;
}

const USER_FACING_NETWORK_MSG = "Something went wrong. Please try again in a moment.";

function getUserFacingMessage(error: unknown): string {
  const msg = error instanceof Error ? error.message : String(error);
  const lower = msg.toLowerCase();
  if (lower.includes("failed to fetch") || lower.includes("network request failed") || lower.includes("load failed")) {
    return USER_FACING_NETWORK_MSG;
  }
  return msg || USER_FACING_NETWORK_MSG;
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showCameraUI, setShowCameraUI] = useState(false);
  const [sourceImageUrl, setSourceImageUrl] = useState<string | null>(null);
  const [initialStoryline, setInitialStoryline] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [characterName, setCharacterName] = useState("Your Friend");
  const [characterModel, setCharacterModel] = useState<CharacterModel | null>(null);
  const [isTalking, setIsTalking] = useState(false);
  const [beats, setBeats] = useState<StoryBeat[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showLongWaitMessage, setShowLongWaitMessage] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [movieUrl, setMovieUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const loadingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isGenerating) {
      setShowLongWaitMessage(false);
      return;
    }
    const timer = setTimeout(() => setShowLongWaitMessage(true), 10000);
    return () => clearTimeout(timer);
  }, [isGenerating]);

  const handleExport = async () => {
    if (!sessionId) return;
    setIsExporting(true);
    setMovieUrl(null);
    setErrorMessage(null);
    try {
      const res = await fetch(`${API_URL}/session/${sessionId}/export`);
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Export failed: ${res.status}`);
      }
      const data = await res.json();
      setMovieUrl(data.movieUrl);
    } catch (error: unknown) {
      console.error("Export failed:", error);
      setErrorMessage(`Oops! Making the movie failed: ${getUserFacingMessage(error)}`);
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
    setErrorMessage(null);
    try {
      // 1. Initialize Session
      const initRes = await fetch(`${API_URL}/session/init`, {
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
      setSourceImageUrl(imageSrc);

      // 2. Upload and Analyze
      const blob = await (await fetch(imageSrc)).blob();
      const analyzeRes = await fetch(`${API_URL}/session/${sessionId}/analyze`, {
        method: 'POST',
        body: blob,
      });

      if (!analyzeRes.ok) {
        throw new Error(`Analyze failed: ${analyzeRes.status}`);
      }

      const data = await analyzeRes.json();
      const profile: CharacterProfile = data.profile;
      const model: CharacterModel = data.model;
      setCharacterName(profile.name || "A New Friend");
      setCharacterModel(model);

      // 3. First beat is triggered by user clicking "Start story" (with optional story idea)
    } catch (error) {
      console.error("Failed to start story:", error);
      setErrorMessage(getUserFacingMessage(error));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const MAX_SCENES = 6;

  const updateBeat = async (sid: string, beatId: string, updates: { narration?: string; sceneTitle?: string }) => {
    try {
      const res = await fetch(`${API_URL}/session/${sid}/beat/${beatId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error("Update failed");
      const updated = await res.json();
      setBeats((prev) => prev.map((b) => (b.id === beatId ? { ...b, ...updated } : b)));
    } catch (e) {
      console.error("Failed to update beat:", e);
      setErrorMessage(getUserFacingMessage(e));
    }
  };

  const deleteBeat = async (sid: string, beatId: string) => {
    try {
      const res = await fetch(`${API_URL}/session/${sid}/beat/${beatId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Delete failed");
      setBeats((prev) => prev.filter((b) => b.id !== beatId));
    } catch (e) {
      console.error("Failed to delete beat:", e);
      setErrorMessage(getUserFacingMessage(e));
    }
  };

  const generateBeat = async (sid: string, instruction?: string, initialStory?: string) => {
    if (beats.length >= MAX_SCENES) return;
    setIsGenerating(true);
    setErrorMessage(null);
    try {
      const params = new URLSearchParams();
      if (instruction) params.set("user_instruction", instruction);
      if (initialStory?.trim()) params.set("initial_storyline", initialStory.trim());
      const qs = params.toString();
      const url = `${API_URL}/session/${sid}/beat${qs ? `?${qs}` : ""}`;

      const beatRes = await fetch(url, { method: 'POST' });
      if (!beatRes.ok) {
        if (beatRes.status === 403) {
          const data = await beatRes.json().catch(() => ({}));
          throw new Error(data.detail || "Maximum scenes reached for this story.");
        }
        throw new Error(`Beat failed: ${beatRes.status}`);
      }
      const beat: StoryBeat = await beatRes.json();
      if (beat && beat.id) {
        setBeats(prev => [...prev, beat]);
      }
    } catch (error) {
      console.error("Failed to generate beat:", error);
      setErrorMessage(getUserFacingMessage(error));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4 md:p-8 bg-[#fff9f0]">
      {errorMessage && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-md flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 shadow-lg">
          <p className="flex-1 text-sm font-medium">{errorMessage}</p>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="flex-shrink-0 p-1 rounded-full hover:bg-amber-200/80 transition-colors"
            aria-label="Dismiss"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}
      {!sessionId ? (
        <div className="w-full max-w-lg flex flex-col items-stretch min-h-[420px]">
          {isAnalyzing ? (
            <div className="w-full flex flex-col items-center justify-center space-y-6 p-6 md:p-8 bg-white rounded-3xl shadow-2xl border border-gray-300 min-h-[420px]">
              <Loader2 className="w-16 h-16 text-sky-500 animate-spin" />
              <h2 className="text-2xl font-bold text-gray-700 font-comic">Looking at your drawing... ✨</h2>
              <p className="text-gray-400 text-center italic">"I think I see a hero in there!"</p>
            </div>
          ) : !showCameraUI ? (
            <LandingIntro onReady={() => setShowCameraUI(true)} />
          ) : (
            <WebcamCapture onCapture={handleCapture} />
          )}
        </div>
      ) : (
        <div className="flex flex-col items-center space-y-8 w-full">
          {sourceImageUrl && (
            <div className="w-full max-w-3xl flex flex-col md:flex-row items-center justify-center gap-12 md:gap-20 p-8 md:px-12 md:py-10 bg-white/90 rounded-3xl border border-gray-300 shadow-xl">
              <div className="flex flex-col items-center gap-3 flex-shrink-0">
                <h3 className="text-lg font-bold text-gray-700 font-comic">Your drawing</h3>
                <div className="w-52 h-52 rounded-xl bg-white shadow-[0_4px_14px_rgba(0,0,0,0.12)] border border-gray-100 overflow-hidden flex items-center justify-center">
                  <img src={sourceImageUrl} alt="Your drawing" className="w-full h-full object-cover" />
                </div>
              </div>
              <div className="flex flex-col items-center justify-center min-h-[200px] flex-shrink-0">
                {isAnalyzing ? (
                  <>
                    <div className="flex items-center gap-3 mb-4">
                      <Paintbrush className="w-10 h-10 text-purple-500 animate-bounce" />
                      <Sparkles className="w-8 h-8 text-amber-500 animate-pulse" />
                      <Paintbrush className="w-10 h-10 text-purple-500 animate-bounce delay-150" />
                    </div>
                    <p className="text-xl font-bold text-sky-700 font-comic text-center">
                      Converting your drawing into a character...
                    </p>
                    <p className="text-gray-500 text-sm mt-2 text-center italic">Something magical is happening!</p>
                  </>
                ) : characterModel ? (
                  <>
                    <p className="text-lg font-bold text-purple-600 font-comic text-center mb-2">
                      {characterName}
                    </p>
                    <div className="w-52 h-52 rounded-xl overflow-hidden flex items-center justify-center bg-white shadow-[0_4px_14px_rgba(0,0,0,0.12)] border border-gray-100">
                      <img
                        src={characterModel.imageUrl}
                        alt={characterName}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          )}

          {characterModel && !sourceImageUrl && (
            <div className="w-full max-w-sm">
              <AnimatedCharacter
                imageUrl={characterModel.imageUrl}
                name={characterName}
                isTalking={isTalking}
              />
            </div>
          )}

          {characterModel && beats.length === 0 && !isGenerating && (
            <div className="w-full max-w-md flex flex-col items-center gap-4 p-6 bg-white/80 rounded-2xl border-2 border-sky-100">
              <label className="text-sm font-bold text-gray-700 font-comic">Story idea (optional)</label>
              <textarea
                value={initialStoryline}
                onChange={(e) => setInitialStoryline(e.target.value)}
                placeholder="e.g. The hero finds a magic key in the forest..."
                className="w-full min-h-[80px] px-4 py-3 rounded-xl border-2 border-sky-200 text-gray-700 placeholder-gray-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-200 outline-none resize-y"
                maxLength={500}
              />
              <button
                onClick={() => sessionId && generateBeat(sessionId, undefined, initialStoryline)}
                className="w-full bg-sky-500 hover:bg-sky-600 text-white py-4 px-6 rounded-xl font-bold shadow-lg transition-all hover:scale-[1.02]"
              >
                Start story
              </button>
            </div>
          )}

          {characterModel && (beats.length > 0 || isGenerating) && (
            <StoryCanvas
              beats={beats}
              characterName={characterName}
              isGenerating={isGenerating}
              isFirstBeat={beats.length === 0}
              showLongWaitMessage={showLongWaitMessage}
              maxScenes={MAX_SCENES}
              onNext={() => sessionId && generateBeat(sessionId)}
              onEditBeat={sessionId ? (beatId, updates) => updateBeat(sessionId, beatId, updates) : undefined}
              onDeleteBeat={sessionId ? (beatId) => deleteBeat(sessionId, beatId) : undefined}
              loadingRef={loadingRef}
            />
          )}
          {characterModel && (
            <GeminiLiveMic
              sessionId={sessionId}
              onStop={handleMicStop}
            />
          )}

          {characterModel && (
          <div className="flex flex-col items-center space-y-4 pt-8">
            <button
              onClick={handleExport}
              disabled={isExporting || beats.length === 0}
              className="bg-green-500 hover:bg-green-600 disabled:bg-gray-300 text-white px-10 py-4 rounded-full font-black text-xl shadow-2xl transition-all hover:scale-105 active:scale-95 flex items-center justify-center gap-3"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin flex-shrink-0" />
                  <span>Making your movie...</span>
                </>
              ) : (
                <>📽️ Export My Movie!</>
              )}
            </button>

            {movieUrl && (
              <a
                href={movieUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sky-600 font-bold underline animate-bounce"
              >
                Click here to see your movie! 🍿
              </a>
            )}
          </div>
          )}
        </div>
      )}
    </main>
  );
}
