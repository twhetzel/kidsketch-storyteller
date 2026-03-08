"use client";

import React from 'react';
import { Sparkles, MessageSquare } from 'lucide-react';

interface StoryBeat {
    id: string;
    narration: string;
    imageUrl: string;
}

interface StoryCanvasProps {
    beats: StoryBeat[];
    characterName: string;
    isGenerating: boolean;
    onNext: () => void;
    loadingRef?: React.RefObject<HTMLDivElement | null>;
}

export const StoryCanvas: React.FC<StoryCanvasProps> = ({ beats, characterName, isGenerating, onNext, loadingRef }) => {
    if (!beats) return null;
    return (
        <div className="flex flex-col space-y-8 w-full max-w-2xl px-4 py-8 bg-white/50 backdrop-blur-sm rounded-3xl min-h-[600px] shadow-2xl border-2 border-white">
            <div className="flex items-center justify-between border-b pb-4">
                <h1 className="text-3xl font-black text-purple-600 drop-shadow-sm font-comic">
                    {characterName}'s Adventure 🏰
                </h1>
                <Sparkles className="text-yellow-400 animate-pulse" />
            </div>

            <div className="space-y-12">
                {beats.filter(b => b && b.id).map((beat, index) => (
                    <div key={beat.id} className="group flex flex-col items-center animate-fade-in-up">
                        <div className="relative w-full aspect-square md:aspect-video rounded-2xl overflow-hidden border-8 border-white shadow-2xl group-hover:scale-[1.02] transition-transform duration-500 transform -rotate-1 lg:-rotate-2">
                            <img src={beat.imageUrl} alt={`Scene ${index + 1}`} className="w-full h-full object-cover" />
                            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-6">
                                <p className="text-white text-lg font-medium leading-relaxed drop-shadow-md italic">
                                    "{beat.narration}"
                                </p>
                            </div>
                        </div>

                        {index < beats.length - 1 && (
                            <div className="h-16 w-1 bg-gradient-to-b from-purple-200 to-transparent mt-4 rounded-full opacity-50" />
                        )}
                    </div>
                ))}

                {isGenerating && (
                    <div ref={loadingRef} className="flex flex-col items-center space-y-4 animate-pulse">
                        <div className="w-full aspect-video bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl border-8 border-dashed border-purple-200 flex flex-col items-center justify-center gap-3">
                            <div className="w-10 h-10 border-4 border-purple-400 border-t-transparent rounded-full animate-spin" />
                            <span className="text-purple-400 font-bold text-lg">Drawing the next scene... 🖌️✨</span>
                        </div>
                    </div>
                )}
            </div>

            {!isGenerating && beats.length > 0 && (
                <div className="sticky bottom-6 flex justify-center w-full">
                    <button
                        onClick={onNext}
                        className="flex items-center space-x-3 bg-purple-600 hover:bg-purple-700 text-white px-8 py-4 rounded-full font-bold shadow-2xl transition-all hover:scale-105 active:scale-95 group"
                    >
                        <MessageSquare className="group-hover:animate-bounce" />
                        <span>Ask for more!</span>
                    </button>
                </div>
            )}
        </div>
    );
};
