"use client";

import React, { useState } from 'react';
import { Sparkles, MessageSquare, Pencil, Trash2 } from 'lucide-react';

interface StoryBeat {
    id: string;
    sceneTitle?: string;
    narration: string;
    imageUrl: string;
}

interface StoryCanvasProps {
    beats: StoryBeat[];
    characterName: string;
    isGenerating: boolean;
    isFirstBeat?: boolean;
    showLongWaitMessage?: boolean;
    maxScenes?: number;
    onNext: () => void;
    onEditBeat?: (beatId: string, updates: { narration?: string; sceneTitle?: string }) => void;
    onDeleteBeat?: (beatId: string) => void;
    loadingRef?: React.RefObject<HTMLDivElement | null>;
}

export const StoryCanvas: React.FC<StoryCanvasProps> = ({ beats, characterName, isGenerating, isFirstBeat, showLongWaitMessage, maxScenes = 15, onNext, onEditBeat, onDeleteBeat, loadingRef }) => {
    const [editingBeatId, setEditingBeatId] = useState<string | null>(null);
    const [editNarration, setEditNarration] = useState("");
    const [editTitle, setEditTitle] = useState("");

    if (!beats) return null;

    const atLimit = maxScenes != null && beats.length >= maxScenes;

    const startEdit = (beat: StoryBeat) => {
        setEditingBeatId(beat.id);
        setEditNarration(beat.narration);
        setEditTitle(beat.sceneTitle ?? "");
    };
    const saveEdit = () => {
        if (editingBeatId && onEditBeat) {
            onEditBeat(editingBeatId, { narration: editNarration.trim() || undefined, sceneTitle: editTitle.trim() || undefined });
        }
        setEditingBeatId(null);
    };
    const cancelEdit = () => {
        setEditingBeatId(null);
    };
    const handleDelete = (beatId: string) => {
        if (onDeleteBeat && (typeof window === "undefined" || window.confirm("Remove this scene?"))) {
            onDeleteBeat(beatId);
        }
    };

    return (
        <div className="flex flex-col space-y-8 w-full max-w-2xl px-4 py-8 bg-white/50 backdrop-blur-sm rounded-3xl min-h-[600px] shadow-2xl border-2 border-white">
            <div className="flex items-center justify-between border-b pb-4">
                <h1 className="text-3xl font-black text-purple-600 drop-shadow-sm font-comic">
                    {characterName}'s Adventure
                </h1>
                <Sparkles className="text-yellow-400 animate-pulse" />
            </div>

            <div className="space-y-12">
                {beats.filter(b => b && b.id).map((beat, index) => (
                    <div key={beat.id} className="group flex flex-col items-center animate-fade-in-up">
                        <div className="relative w-full aspect-square md:aspect-video rounded-2xl overflow-hidden border-8 border-white shadow-2xl group-hover:scale-[1.02] transition-transform duration-500 transform -rotate-1 lg:-rotate-2">
                            <img src={beat.imageUrl} alt={`Scene ${index + 1}`} className="w-full h-full object-cover" />
                            {(onEditBeat || onDeleteBeat) && (
                                <div className="absolute top-2 right-2 flex gap-2 z-10">
                                    {onEditBeat && (
                                        <button
                                            onClick={() => startEdit(beat)}
                                            className="p-2 rounded-full bg-white/90 text-purple-600 hover:bg-white shadow"
                                            aria-label="Edit scene"
                                        >
                                            <Pencil size={18} />
                                        </button>
                                    )}
                                    {onDeleteBeat && (
                                        <button
                                            onClick={() => handleDelete(beat.id)}
                                            className="p-2 rounded-full bg-white/90 text-red-600 hover:bg-white shadow"
                                            aria-label="Delete scene"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    )}
                                </div>
                            )}
                            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-6">
                                {editingBeatId === beat.id ? (
                                    <div className="space-y-2">
                                        <input
                                            value={editTitle}
                                            onChange={(e) => setEditTitle(e.target.value)}
                                            placeholder="Scene title"
                                            className="w-full px-2 py-1 rounded bg-white/90 text-gray-800 font-medium text-sm"
                                        />
                                        <textarea
                                            value={editNarration}
                                            onChange={(e) => setEditNarration(e.target.value)}
                                            className="w-full px-2 py-1 rounded bg-white/90 text-gray-800 text-base min-h-[60px] resize-y"
                                            placeholder="Narration"
                                        />
                                        <div className="flex gap-2">
                                            <button onClick={saveEdit} className="px-3 py-1 rounded bg-green-600 text-white text-sm font-bold">Save</button>
                                            <button onClick={cancelEdit} className="px-3 py-1 rounded bg-gray-500 text-white text-sm font-bold">Cancel</button>
                                        </div>
                                    </div>
                                ) : (
                                    <p className="text-white text-lg font-medium leading-relaxed drop-shadow-md italic">
                                        "{beat.narration}"
                                    </p>
                                )}
                            </div>
                        </div>

                        {index < beats.length - 1 && (
                            <div className="h-16 w-1 bg-gradient-to-b from-purple-200 to-transparent mt-4 rounded-full opacity-50" />
                        )}
                    </div>
                ))}

                {isGenerating && (
                    <div ref={loadingRef} className="flex flex-col items-center space-y-4">
                        <div className="w-full aspect-video bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl border-8 border-dashed border-purple-200 flex flex-col items-center justify-center gap-3">
                            <div className="w-10 h-10 border-4 border-purple-400 border-t-transparent rounded-full animate-spin" />
                            <span className="text-purple-400 font-bold text-lg">
                                {isFirstBeat ? 'Creating your first scene...' : 'Drawing the next scene...'} 🖌️✨
                            </span>
                            {showLongWaitMessage && (
                                <span className="text-purple-500/90 text-sm font-medium">Taking a bit longer to draw this scene...</span>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {!isGenerating && beats.length > 0 && (
                <div className="sticky bottom-6 flex flex-col items-center gap-2 w-full">
                    {atLimit ? (
                        <p className="text-gray-500 font-medium">Maximum scenes reached for this story.</p>
                    ) : (
                        <button
                            onClick={onNext}
                            className="flex items-center space-x-3 bg-purple-600 hover:bg-purple-700 text-white px-8 py-4 rounded-full font-bold shadow-2xl transition-all hover:scale-105 active:scale-95 group"
                        >
                            <MessageSquare className="group-hover:animate-bounce" />
                            <span>Ask for more!</span>
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};
