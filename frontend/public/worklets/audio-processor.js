/**
 * AudioWorkletProcessor for converting Float32 audio to 16-bit PCM.
 * Runs in a separate thread to avoid blocking the main UI thread.
 */
class AudioProcessor extends AudioWorkletProcessor {
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0];

            // Convert Float32 to Int16 PCM
            const int16Buffer = new Int16Array(channelData.length);
            for (let i = 0; i < channelData.length; i++) {
                const s = Math.max(-1, Math.min(1, channelData[i]));
                int16Buffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Send the PCM data back to the main thread
            this.port.postMessage(int16Buffer.buffer, [int16Buffer.buffer]);
        }
        return true; // Keep the processor alive
    }
}

registerProcessor('audio-processor', AudioProcessor);
