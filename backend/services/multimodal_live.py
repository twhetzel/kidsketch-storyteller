import os
import asyncio
import json
import base64
import websockets
from typing import Optional

class MultimodalLiveBridge:
    """
    A bridge between the Client WebSocket (Frontend) and the Gemini Multimodal Live API WebSocket.
    """
    GEMINI_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = f"{self.GEMINI_URL}?key={self.api_key}"

    async def run(self, client_websocket, session_id: str, context_prompt: str):
        """
        Main loop to pipe audio/text between client and Gemini.
        """
        async with websockets.connect(self.url) as gemini_ws:
            # 1. Send setup - native audio model requires response_modalities: AUDIO
            setup_msg = {
                "setup": {
                    "model": "models/gemini-2.5-flash-native-audio-latest",
                    "generation_config": {
                        "response_modalities": ["AUDIO"]
                    },
                    "output_audio_transcription": {},
                    "input_audio_transcription": {},
                    "system_instruction": {
                        "parts": [{
                            "text": context_prompt + "\n\nAfter each response, if the child's request implies they want to go somewhere new or do a new action, end your response with exactly: [NEW_SCENE]"
                        }]
                    }
                }
            }
            await gemini_ws.send(json.dumps(setup_msg))
            
            # Wait for setup complete response from Gemini
            setup_resp = await gemini_ws.recv()
            print(f"✅ Gemini Live session ready. Response: {setup_resp[:150]}")

            # 2. Bi-directional proxy using tasks so cancellation propagates correctly
            client_task = None
            gemini_task = None

            async def client_to_gemini():
                try:
                    while True:
                        message = await client_websocket.receive()
                        # Check for disconnect signal
                        if message.get("type") == "websocket.disconnect":
                            print("ℹ️ Client disconnected cleanly")
                            break
                        if "bytes" in message:
                            audio_b64 = base64.b64encode(message["bytes"]).decode('utf-8')
                            realtime_msg = {
                                "realtimeInput": {
                                    "mediaChunks": [
                                        {
                                            "data": audio_b64,
                                            "mimeType": "audio/pcm;rate=16000"
                                        }
                                    ]
                                }
                            }
                            await gemini_ws.send(json.dumps(realtime_msg))
                        elif "text" in message and message["text"]:
                            # Sanitize and wrap text into the Gemini protocol structure 
                            # to prevent clients from sending arbitrary protocol-level commands.
                            safe_text = str(message["text"])[:2000]
                            realtime_text = {
                                "clientContent": {
                                    "turns": [
                                        {
                                            "role": "user",
                                            "parts": [{"text": safe_text}]
                                        }
                                    ]
                                }
                            }
                            await gemini_ws.send(json.dumps(realtime_text))
                except (Exception, websockets.exceptions.ConnectionClosed) as e:
                    print(f"ℹ️ Client connection ended: {e}")
                finally:
                    if gemini_task and not gemini_task.done():
                        gemini_task.cancel()

            async def gemini_to_client():
                try:
                    async for message in gemini_ws:
                        try:
                            if isinstance(message, str):
                                await client_websocket.send_text(message)
                            else:
                                await client_websocket.send_bytes(message)
                        except Exception:
                            break  # Client likely disconnected
                except Exception as e:
                    print(f"ℹ️ Gemini connection ended: {e}")
                finally:
                    if client_task and not client_task.done():
                        client_task.cancel()

            loop = asyncio.get_event_loop()
            client_task = loop.create_task(client_to_gemini())
            gemini_task = loop.create_task(gemini_to_client())

            try:
                await asyncio.gather(client_task, gemini_task)
            except asyncio.CancelledError:
                pass  # Clean shutdown
