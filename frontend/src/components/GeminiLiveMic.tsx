"use client";

import React, { useRef, useState, useCallback } from 'react';
import { Mic, MicOff } from 'lucide-react';

interface GeminiLiveMicProps {
    sessionId: string;
    onStop?: (transcript: string) => void;
}

const TARGET_SAMPLE_RATE = 16000;

export const GeminiLiveMic: React.FC<GeminiLiveMicProps> = ({ sessionId, onStop }) => {
    const [isActive, setIsActive] = useState(false);
    const [transcript, setTranscript] = useState('');

    const socketRef = useRef<WebSocket | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const processorRef = useRef<AudioWorkletNode | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const recognitionRef = useRef<any>(null);
    const transcriptRef = useRef<string>('');  // Keep ref in sync for closure access
    const stopCalledRef = useRef(false);       // Guard against double-trigger

    const cleanup = useCallback(() => {
        processorRef.current?.disconnect();
        processorRef.current = null;
        audioContextRef.current?.close();
        audioContextRef.current = null;
        streamRef.current?.getTracks().forEach(t => t.stop());
        streamRef.current = null;
        recognitionRef.current?.stop();
        recognitionRef.current = null;
        socketRef.current = null;
        setIsActive(false);
    }, []);

    const triggerStop = useCallback(() => {
        if (stopCalledRef.current) return; // Prevent double-trigger
        stopCalledRef.current = true;

        const finalTranscript = transcriptRef.current.trim() || 'Tell me what happens next!';
        console.log("🎙️ Mic stopped. Transcript:", finalTranscript);
        transcriptRef.current = '';
        setTranscript('');
        onStop?.(finalTranscript);
    }, [onStop]);

    const stopSession = useCallback(() => {
        // Close WebSocket first (will trigger onclose)
        if (socketRef.current) {
            socketRef.current.onclose = null; // Remove onclose so it doesn't double-trigger
            socketRef.current.close();
        }
        cleanup();
        triggerStop();
    }, [cleanup, triggerStop]);

    const toggleMic = () => {
        if (isActive) {
            stopSession();
        } else {
            startSession();
        }
    };

    const startSession = async () => {
        stopCalledRef.current = false;
        transcriptRef.current = '';
        setTranscript('');

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            streamRef.current = stream;
            setIsActive(true);

            // --- Web Speech API for reliable local transcript ---
            const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
            if (SpeechRecognition) {
                const recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';
                recognitionRef.current = recognition;

                recognition.onresult = (event: any) => {
                    let interim = '';
                    let final = transcriptRef.current;
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        if (event.results[i].isFinal) {
                            final += ' ' + event.results[i][0].transcript;
                        } else {
                            interim = event.results[i][0].transcript;
                        }
                    }
                    transcriptRef.current = final.trim();
                    setTranscript((final + (interim ? ' ' + interim : '')).trim());
                };
                recognition.onerror = (e: any) => console.warn('Speech recognition error:', e.error);
                recognition.start();
                console.log("🎤 Web Speech API started");
            } else {
                console.warn("⚠️ Web Speech API not available — transcript will be empty");
            }

            // --- Setup Audio Early (Must be linked to user gesture) ---
            const audioCtx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
            audioContextRef.current = audioCtx;

            // Resume context immediately in case it started suspended
            if (audioCtx.state === 'suspended') {
                await audioCtx.resume();
            }

            // Load the AudioWorklet module
            await audioCtx.audioWorklet.addModule('/worklets/audio-processor.js');

            // --- Gemini Live WebSocket for voice interaction ---
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const wsUrl = apiUrl.replace(/^http/, 'ws') + `/ws/live/${sessionId}`;
            const ws = new WebSocket(wsUrl);
            socketRef.current = ws;

            ws.onopen = async () => {
                console.log("✅ Gemini WebSocket connected");
                try {
                    const source = audioCtx.createMediaStreamSource(stream);
                    const processor = new AudioWorkletNode(audioCtx, 'audio-processor');
                    processorRef.current = processor;

                    processor.port.onmessage = (event) => {
                        if (ws.readyState === WebSocket.OPEN) {
                            ws.send(event.data);
                        }
                    };

                    source.connect(processor);
                    processor.connect(audioCtx.destination);
                    console.log("🎙️ AudioWorklet PCM streaming started at 16kHz");
                } catch (err) {
                    console.error("❌ Audio connection logic failed:", err);
                    cleanup();
                }
            };

            ws.onerror = (error) => {
                console.error("⚠️ WebSocket Error:", error);
                ws.onclose = null;
                cleanup();
                // Don't trigger scene generation on error
            };

            ws.onclose = (event) => {
                console.log("ℹ️ WebSocket closed:", event.code, event.reason);
                // onclose is removed before intentional stops (in stopSession)
                // so this path only fires for unexpected disconnects
                cleanup();
            };

        } catch (err) {
            console.error("Microphone access denied:", err);
            alert("I need your microphone to hear you! 🎙️");
            setIsActive(false);
        }
    };

    return (
        <div className="flex flex-col items-center space-y-4">
            <button
                onClick={toggleMic}
                className={`group relative p-8 rounded-full shadow-[0_0_50px_rgba(0,0,0,0.1)] transition-all hover:scale-110 active:scale-95 ${isActive
                    ? 'bg-red-500 text-white'
                    : 'bg-white text-purple-600 border-4 border-purple-50'
                    }`}
            >
                {isActive && (
                    <div className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-20"></div>
                )}
                {isActive ? <Mic size={40} /> : <MicOff size={40} />}
            </button>
            <div className="text-center space-y-2 w-full max-w-lg">
                <span className={`text-sm font-black uppercase tracking-widest ${isActive ? 'text-red-500' : 'text-gray-400'}`}>
                    {isActive ? 'Listening...' : 'Tap to talk'}
                </span>
                {isActive && (
                    <div className="min-h-[4rem] rounded-xl bg-white/80 border-2 border-purple-100 p-4 text-left">
                        <p className="text-lg text-gray-700 font-medium leading-relaxed">
                            {transcript ? `"${transcript}"` : '...'}
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};
