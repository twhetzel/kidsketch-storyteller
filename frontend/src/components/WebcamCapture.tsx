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
    const [cameraStarted, setCameraStarted] = useState(false);

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

    const startCamera = () => {
        setCameraStarted(true);
    };

    return (
        <div className="w-full flex flex-col items-center gap-6 min-h-[420px] p-6 md:p-8 bg-white rounded-3xl shadow-2xl border border-gray-300">
            <h2 className="text-3xl font-black text-purple-600 font-comic text-center flex-shrink-0">Show me your drawing! 🎨</h2>

            {!imgSrc ? (
                !cameraStarted ? (
                    <div className="flex flex-col items-center w-full flex-1 min-h-0">
                        <p className="text-gray-700 text-center font-medium flex-shrink-0">
                            Click start camera, then hold your drawing in the frame and tap the button to capture.
                        </p>
                        <div className="flex-1 min-h-4 w-full" />
                        <button
                            onClick={startCamera}
                            className="w-full flex items-center justify-center gap-2 bg-sky-500 hover:bg-sky-600 text-white py-4 px-6 rounded-xl font-bold shadow-lg transition-all hover:scale-[1.02] flex-shrink-0"
                        >
                            <Camera size={24} />
                            Start camera
                        </button>
                    </div>
                ) : (
                <div className="relative w-full rounded-xl overflow-hidden border-4 border-purple-200">
                    <Webcam
                        audio={false}
                        ref={webcamRef}
                        screenshotFormat="image/png"
                        className="w-full h-auto"
                    />
                    <button
                        onClick={capture}
                        className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-sky-500 hover:bg-sky-600 text-white p-4 rounded-full shadow-lg transition-transform hover:scale-110"
                    >
                        <Camera size={28} />
                    </button>
                </div>
            ) ) : (
                <div className="flex flex-col items-center space-y-4">
                    <img src={imgSrc} alt="Captured drawing" className="w-full rounded-xl border-4 border-green-400 shadow-inner" />
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
