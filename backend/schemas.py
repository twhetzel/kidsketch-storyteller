from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

class CharacterProfile(BaseModel):
    name: str
    description: str
    visualTraits: List[str] = Field(default_factory=list)

class CharacterModel(BaseModel):
    imageUrl: str    # Polished version from Imagen 3
    traits: List[str] # Detailed visual consistency cues
    basePrompt: str  # The prompt that generated this look

class StoryBeat(BaseModel):
    id: str
    sceneTitle: str
    narration: str
    audioUrl: str
    imagePrompt: str
    imageUrl: str
    timestamp: float

class StoryState(BaseModel):
    sessionId: str
    sourceSketchUrl: str
    characterProfile: CharacterProfile
    characterModel: Optional[CharacterModel] = None # The polished visual identity
    currentSetting: str
    narrativeTone: str
    continuityFacts: List[str] = Field(default_factory=list)
    history: List[StoryBeat] = Field(default_factory=list)

class ShotPlan(BaseModel):
    id: str
    type: str # 'intro', 'adventure', 'climax', 'ending'
    bgImageUrl: str
    audioUrl: str = "" # Narration audio from gTTS
    narration: str
    motionDirection: str # e.g., 'zoom-in', 'pan-left'
    bgPrompt: str = "" # Prompt for background generation

class MoviePlan(BaseModel):
    shots: List[ShotPlan] = Field(default_factory=list)

class StoryPlan(BaseModel):
    currentSetting: str
    narrativeTone: str 
    narrativeArc: List[str] = Field(default_factory=list)
    currentGoalIndex: int = 0
