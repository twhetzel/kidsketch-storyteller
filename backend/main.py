import os
from uuid import uuid4
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from schemas import StoryState, StoryPlan, CharacterProfile, StoryBeat, CharacterModel
from services.story_agent import StoryAgent
from services.image_gen import ImageGenService
from services.storage import StorageService
from services.multimodal_live import MultimodalLiveBridge
from services.video_engine import VideoEngine

load_dotenv()

app = FastAPI(title="KidSketch Storyteller API")

# Initialize services
story_agent = StoryAgent(api_key=os.getenv("GEMINI_API_KEY", "").strip())
image_gen = ImageGenService(project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "").strip())
storage_service = StorageService(bucket_name=os.getenv("GCS_BUCKET_NAME", "").strip())
live_bridge = MultimodalLiveBridge(api_key=os.getenv("GEMINI_API_KEY", "").strip())
video_engine = VideoEngine(storage_service=storage_service)

# CORS for Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For hackathon, allow all. Restrict later if needed.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# In-memory session store: sessionId -> StoryState
sessions = {}

@app.get("/")
async def root():
    return {"message": "KidSketch Agent is ready!"}

class SessionInitRequest(BaseModel):
    sketch_url: str

@app.post("/session/init")
async def initialize_session(req: SessionInitRequest):
    session_id = str(uuid4())
    
    # In a real flow, we'd download the sketch_url or receive bytes
    # For now, we'll simulate the analysis or assume it's done via a separate byte-upload
    # Let's add an optional bytes upload for the actual sketch
    
    new_state = StoryState(
        sessionId=session_id,
        sourceSketchUrl=req.sketch_url,
        characterProfile=CharacterProfile(name="Friend", description="A new friend", visualTraits=[]),
        currentSetting="A magical starting place",
        narrativeTone="Whimsical",
        continuityFacts=[],
        history=[]
    )
    
    sessions[session_id] = new_state
    return {"sessionId": session_id, "state": new_state}

@app.post("/session/{session_id}/analyze")
async def analyze_sketch(session_id: str, request: Request):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 1. Analyze raw drawing
    image_bytes = await request.body()
    
    # Upload original sketch to GCS for fallback use
    sketch_path = f"sessions/{session_id}/sketch.png"
    sessions[session_id].sourceSketchUrl = await storage_service.upload_bytes(image_bytes, sketch_path)
    
    profile = await story_agent.analyze_drawing(image_bytes)
    sessions[session_id].characterProfile = profile
    
    # 2. Generate Polished Character Design
    design_data = await story_agent.generate_character_prompt(profile)
    
    # 3. Generate Character Image (Imagen 3)
    local_char_path = f"/tmp/{session_id}_character.png"
    gen_char_path = await image_gen.generate_image(design_data["visualPrompt"], local_char_path)
    
    # 4. Upload to GCS
    if gen_char_path:
        remote_char_path = f"sessions/{session_id}/character_model.png"
        char_url = await storage_service.upload_file(local_char_path, remote_char_path)
    else:
        # Fallback: Use the original sketch if Imagen 3 fails
        char_url = sessions[session_id].sourceSketchUrl if sessions[session_id].sourceSketchUrl != "pending" else "https://placehold.co/600x400?text=Drawing+in+progress...🎨"
    
    # 5. Store CharacterModel
    char_model = CharacterModel(
        imageUrl=char_url,
        traits=design_data["detailedTraits"],
        basePrompt=design_data["visualPrompt"]
    )
    sessions[session_id].characterModel = char_model
    
    return {
        "profile": profile,
        "model": char_model
    }

@app.post("/session/{session_id}/beat")
async def create_story_beat(session_id: str, user_instruction: Optional[str] = None):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    # For MVP, we'll maintain a simple plan alongside the state
    plan = getattr(state, "_plan", StoryPlan(
        currentSetting=state.currentSetting, 
        narrativeTone=state.narrativeTone,
        narrativeArc=["Meet the hero", "A sudden problem", "A magical solution", "A happy ending"],
        currentGoalIndex=0
    ))
    
    current_goal = plan.narrativeArc[min(plan.currentGoalIndex, len(plan.narrativeArc)-1)]
    
    # 1. Update narrative if instruction exists
    if user_instruction:
        await story_agent.update_narrative(state, plan, user_instruction)
    
    # 2. Generate next beat (Narration + Image Prompt)
    # Use refined character model traits for visual consistency if available
    traits = state.characterModel.traits if state.characterModel else state.characterProfile.visualTraits
    
    beat = await story_agent.generate_next_beat(
        state, 
        plan, 
        user_input=user_instruction if user_instruction else f"Continue the story: {current_goal}"
    )
    
    # 3. Generate Visual
    # Inject character traits into the image prompt for better consistency
    if state.characterModel:
        beat.imagePrompt = f"{beat.imagePrompt}. Focus on the character: {', '.join(traits)}"
    
    local_img_path = f"/tmp/{beat.id}.png"
    gen_path = await image_gen.generate_image(beat.imagePrompt, local_img_path)
    
    # 4. Upload Visual to GCS (or use fallback if generation failed)
    if gen_path:
        remote_img_path = f"sessions/{session_id}/beats/{beat.id}.png"
        beat.imageUrl = await storage_service.upload_file(local_img_path, remote_img_path)
    else:
        # Fallback for quota limits: use a high-quality placeholder or the original sketch
        beat.imageUrl = state.sourceSketchUrl if state.sourceSketchUrl != "pending" else "https://placehold.co/600x400?text=Drawing+in+progress...🎨"
    
    # Update State
    state.history.append(beat)
    plan.currentGoalIndex += 1
    state._plan = plan # Store plan back in session
    
    return beat

@app.websocket("/ws/live/{session_id}")
async def live_voice_endpoint(websocket: WebSocket, session_id: str):
    if session_id not in sessions:
        await websocket.close(code=1008)
        return

    state = sessions[session_id]
    await websocket.accept()
    
    # Context prompt for the "character"
    context = f"""
    You are {state.characterProfile.name}, a character in a children's story.
    Description: {state.characterProfile.description}
    World: {state.currentSetting}
    Tone: {state.narrativeTone}
    Known Facts: {", ".join(state.continuityFacts)}
    
    The child is talking to you. Stay in character! 
    Keep your responses short, friendly, and encouraging.
    If the child asks you to do something or go somewhere, agree and describe it simply.
    """
    
    await live_bridge.run(websocket, session_id, context)

@app.get("/session/{session_id}/export")
async def export_movie(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    if not state.history:
        return {"error": "No story beats to export"}
    
    from gtts import gTTS
    from schemas import MoviePlan, ShotPlan
    
    # Build movie shots DIRECTLY from the user's actual story beats
    # This ensures the movie matches exactly what the user created
    shots = []
    motion_cycle = ['zoom-in', 'pan-right', 'zoom-out', 'pan-left']
    
    for i, beat in enumerate(state.history):
        shot = ShotPlan(
            id=beat.id,
            type="story",
            bgImageUrl=beat.imageUrl,
            narration=beat.narration,
            motionDirection=motion_cycle[i % len(motion_cycle)],
            bgPrompt=""  # Already generated
        )
        shots.append(shot)
    
    movie_plan = MoviePlan(shots=shots)

    # Generate Audio (TTS) for each shot narration
    for i, shot in enumerate(movie_plan.shots):
        local_audio_path = f"/tmp/{session_id}_shot_{i}.mp3"
        try:
            tts = gTTS(text=shot.narration, lang='en', slow=False)
            tts.save(local_audio_path)
            remote_audio_path = f"sessions/{session_id}/movie_shots/{shot.id}.mp3"
            shot.audioUrl = await storage_service.upload_file(local_audio_path, remote_audio_path)
        except Exception as e:
            print(f"TTS Failed for shot {i}: {e}")
            shot.audioUrl = ""
        
    # Create Animated Movie with FFmpeg
    output_path = f"/tmp/{session_id}_living_movie.mp4"
    try:
        await video_engine.create_animated_movie(session_id, movie_plan, output_path)
        remote_path = f"sessions/{session_id}/living_movie.mp4"
        url = await storage_service.upload_file(output_path, remote_path)
        return {"movieUrl": url}
    except Exception as e:
        print(f"Export Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
