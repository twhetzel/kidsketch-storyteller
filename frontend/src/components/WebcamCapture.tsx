"use client";

import React, { useRef, useState, useCallback } from 'react';
import Webcam from 'react-webcam';
import { Camera, RefreshCw, Check } from 'lucide-react';

interface WebcamCaptureProps {
    onCapture: (imageSrc: string) => void;
}

export const WebcamCapture: React.FC<WebcamCaptureProps> = ({ onCapture }) => {
    const webcamRef = useRef<Webcam>(null);
    const [imgSrc, setImgSrc] = useState<string | null>(null);

    const capture = useCallback(() => {
        const imageSrc = webcamRef.current?.getScreenshot();
        if (imageSrc) {
            setImgSrc(imageSrc);
        }
    }, [webcamRef]);

    const retake = () => setImgSrc(null);

    const confirm = () => {
        if (imgSrc) {
            onCapture(imgSrc);
        }
    };

    return (
        <div className="flex flex-col items-center space-y-4 p-6 bg-white rounded-2xl shadow-xl border-4 border-yellow-200">
            <h2 className="text-2xl font-bold text-gray-800 font-comic">Show me your drawing! 🎨</h2>

            {!imgSrc ? (
                <div className="relative rounded-xl overflow-hidden border-4 border-blue-400">
                    <Webcam
                        audio={false}
                        ref={webcamRef}
                        screenshotFormat="image/png"
                        className="w-full max-w-md h-auto"
                    />
                    <button
                        onClick={capture}
                        className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-blue-500 hover:bg-blue-600 text-white p-4 rounded-full shadow-lg transition-transform hover:scale-110"
                    >
                        <Camera size={28} />
                    </button>
                </div>
            ) : (
                <div className="flex flex-col items-center space-y-4">
                    <img src={imgSrc} alt="Captured drawing" className="rounded-xl border-4 border-green-400 max-w-md shadow-inner" />
                    <div className="flex space-x-4">
                        <button
                            onClick={retake}
                            className="flex items-center space-x-2 bg-gray-200 hover:bg-gray-300 text-gray-700 px-6 py-2 rounded-full font-bold shadow transition-all"
                        >
                            <RefreshCw size={20} />
                            <span>Retake</span>
                        </button>
                        <button
                            onClick={confirm}
                            className="flex items-center space-x-2 bg-green-500 hover:bg-green-600 text-white px-8 py-2 rounded-full font-bold shadow-lg transition-all hover:scale-105"
                        >
                            <Check size={20} />
                            <span>It's perfect!</span>
                        </button>
                    </div>
                </div>
            )}
            <p className="text-gray-500 text-sm">Hold your drawing steady in front of the camera!</p>
        </div>
    );
};
