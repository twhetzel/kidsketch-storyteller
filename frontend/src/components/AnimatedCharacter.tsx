"use client";

import React from 'react';

interface AnimatedCharacterProps {
    imageUrl: string;
    name: string;
    isTalking?: boolean;
}

export const AnimatedCharacter: React.FC<AnimatedCharacterProps> = ({ imageUrl, name, isTalking }) => {
    return (
        <div className="relative group cursor-pointer">
            {/* The main card/frame */}
            <div className={`relative aspect-square rounded-[3rem] overflow-hidden border-[12px] border-white shadow-2xl transition-all duration-700 transform ${isTalking ? 'scale-105 rotate-1 shadow-purple-200' : 'hover:scale-102 hover:-rotate-1'
                } animate-float`}>

                {/* Background Glow */}
                <div className={`absolute inset-0 bg-gradient-to-tr transition-opacity duration-500 ${isTalking ? 'from-purple-500/20 to-pink-500/10 opacity-100' : 'from-blue-500/5 to-purple-500/5 opacity-0'
                    }`} />

                {/* Character Image */}
                <img
                    src={imageUrl}
                    alt={name}
                    className={`w-full h-full object-cover transition-transform duration-700 ${isTalking ? 'scale-110' : 'scale-100'
                        }`}
                />

                {/* Animation Overlays (Simplistic approach for Hackathon) */}
                <div className="absolute inset-0 pointer-events-none">
                    {/* Blinking Overlay */}
                    <div className="absolute top-[20%] left-0 w-full h-[60%] flex justify-around px-8 opacity-0 group-hover:animate-blink pointer-events-none">
                        <div className="w-12 h-2 bg-black/20 rounded-full blur-[1px]" />
                        <div className="w-12 h-2 bg-black/20 rounded-full blur-[1px]" />
                    </div>

                    {/* Talking Mouth Overlay */}
                    {isTalking && (
                        <div className="absolute bottom-[25%] left-1/2 -translate-x-1/2 w-16 h-8 bg-black/10 rounded-full blur-[2px] animate-talk" />
                    )}
                </div>

                {/* Name Tag */}
                <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-white/90 backdrop-blur-md px-6 py-2 rounded-full shadow-lg border-2 border-purple-100">
                    <span className="text-xl font-black text-purple-600 font-comic tracking-tight">
                        {name}
                    </span>
                </div>
            </div>

            {/* Reflection / Shadow */}
            <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-[80%] h-4 bg-black/5 blur-xl rounded-full" />
        </div>
    );
};
