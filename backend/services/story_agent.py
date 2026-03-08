import os
import json
import google.generativeai as genai
from uuid import uuid4
from typing import Optional
from schemas import StoryState, StoryPlan, CharacterProfile, StoryBeat, CharacterModel, MoviePlan, ShotPlan

class StoryAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.analysis_model = genai.GenerativeModel('gemini-2.0-flash')

    def _parse_json(self, response_text: str, fallback_data: dict) -> dict:
        """
        Robustly parses JSON from LLM response, handling common formatting quirks.
        """
        try:
            # Clean up potential markdown blocks if they slip through despite JSON mode
            content = response_text.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            if isinstance(result, list) and len(result) > 0:
                return result[0] if isinstance(result[0], dict) else fallback_data
            return result if isinstance(result, dict) else fallback_data
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Error parsing JSON response: {e}\nRaw Response: {response_text}")
            return fallback_data

    async def analyze_drawing(self, image_data: bytes) -> CharacterProfile:
        """
        Analyzes the uploaded sketch to create a structured character profile.
        """
        prompt = """
        You are a creative character designer for children's stories. 
        Analyze this drawing and provide a character profile in JSON format:
        {
            "name": "a name for the character",
            "description": "a friendly 2-sentence description",
            "visualTraits": ["trait 1", "trait 2"]
        }
        Focus on identifying the core creature/object and its personality.
        """
        
        try:
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/png", "data": image_data}],
                generation_config={"response_mime_type": "application/json"}
            )
            data = self._parse_json(response.text, {})
            return CharacterProfile(
                name=data.get("name", "Hero"),
                description=data.get("description", "A brave new friend."),
                visualTraits=data.get("visualTraits", ["kind eyes", "cheerful"])
            )
        except Exception as e:
            print(f"Error during AI analysis or parsing: {e}")
            return CharacterProfile(name="Hero", description="A brave new friend.", visualTraits=["kind eyes", "cheerful"])

    async def generate_character_prompt(self, profile: CharacterProfile) -> dict:
        """
        Creates a high-quality Imagen 3 prompt and detailed visual traits for the CharacterModel.
        """
        prompt = f"""
        Based on this character profile:
        Name: {profile.name}
        Description: {profile.description}
        Initial Traits: {", ".join(profile.visualTraits)}

        Create a detailed visual description for a high-quality 3D character model in a modern animation style (like Pixar or Dreamworks).
        Return JSON with:
        "visualPrompt": (comprehensive prompt for Imagen 3),
        "detailedTraits": (list of specific visual details for consistency)
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = self._parse_json(response.text, {})
            
            # Ensure detailedTraits is a list of strings (AI sometimes returns objects)
            traits = data.get("detailedTraits", [])
            sanitized_traits = []
            if isinstance(traits, list):
                for t in traits:
                    if isinstance(t, dict):
                        # Convert {'trait': 'name', 'description': 'val'} to "name: val"
                        name = t.get("trait") or t.get("name") or "Detail"
                        desc = t.get("description") or t.get("value") or ""
                        sanitized_traits.append(f"{name}: {desc}" if desc else name)
                    else:
                        sanitized_traits.append(str(t))
            
            return {
                "visualPrompt": data.get("visualPrompt", f"A friendly character named {profile.name}, {profile.description}, vibrant colors, high quality animation style."),
                "detailedTraits": sanitized_traits or profile.visualTraits
            }
        except Exception as e:
            print(f"Error generating character prompt: {e}")
            return {
                "visualPrompt": f"A friendly character named {profile.name}, {profile.description}, vibrant colors, high quality animation style.",
                "detailedTraits": profile.visualTraits
            }

    async def generate_next_beat(self, state: StoryState, plan: StoryPlan, user_input: Optional[str] = None) -> StoryBeat:
        """
        Generates the next interleaved story beat (narration + image prompt).
        """
        prompt = f"""
        You are an expert storyteller for kids. 
        Current Setting: {state.currentSetting}
        Narrative Tone: {state.narrativeTone}
        Known Facts: {", ".join(state.continuityFacts)}
        Character: {state.characterProfile.name} ({state.characterProfile.description})
        
        Generate the next beat of the story. 
        Return JSON with:
        "sceneTitle": (short creative title),
        "narration": (short, kid-friendly),
        "imagePrompt": (highly descriptive for Imagen 3 art generation).
        Keep the character's traits: {", ".join(state.characterProfile.visualTraits)}.
        """
        
        if user_input:
            # User instruction takes highest priority — the scene must reflect it
            prompt = f"""
        You are an expert storyteller for kids.
        Character: {state.characterProfile.name} ({state.characterProfile.description})
        Visual traits: {", ".join(state.characterProfile.visualTraits)}
        Known Facts: {", ".join(state.continuityFacts) or 'None yet'}
        
        THE CHILD JUST SAID: "{user_input}"
        
        Create the NEXT story scene that directly responds to and incorporates what the child just said.
        The scene MUST reflect the child's direction — if they said "go to the moon", the character goes to the moon.
        
        Return JSON with:
        "sceneTitle": (short creative title based on child's instruction),
        "narration": (1-2 sentences, kid-friendly, directly connected to what they said),
        "imagePrompt": (highly descriptive Imagen 3 prompt showing the character in the new scene the child described).
        Keep consistent character visuals: {", ".join(state.characterProfile.visualTraits)}.
        """
        else:
            prompt = f"""
        You are an expert storyteller for kids. 
        Current Setting: {state.currentSetting}
        Narrative Tone: {state.narrativeTone}
        Known Facts: {", ".join(state.continuityFacts) or 'None yet'}
        Character: {state.characterProfile.name} ({state.characterProfile.description})
        
        Generate the next beat of the story. 
        Return JSON with:
        "sceneTitle": (short creative title),
        "narration": (short, kid-friendly),
        "imagePrompt": (highly descriptive for Imagen 3 art generation).
        Keep the character's traits: {", ".join(state.characterProfile.visualTraits)}.
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = self._parse_json(response.text, {})
            
            return StoryBeat(
                id=str(uuid4()),
                sceneTitle=data.get("sceneTitle", "A New Chapter"),
                narration=data.get("narration", "Something magical happens!"),
                audioUrl="", # To be filled by TTS or real-time voice
                imagePrompt=data.get("imagePrompt", "A magical scene in a children's storybook"),
                imageUrl="", # To be filled by ImageGen
                timestamp=0.0
            )
        except Exception as e:
            print(f"Error generating beat: {e}")
            return StoryBeat(
                id=str(uuid4()), 
                sceneTitle="A New Chapter", 
                narration="Something magical happens!", 
                audioUrl="", 
                imagePrompt="A magical scene in a children's storybook", 
                imageUrl="", 
                timestamp=0.0
            )

    async def update_narrative(self, state: StoryState, plan: StoryPlan, instruction: str):
        """
        Updates the StoryPlan and StoryState.continuityFacts based on user instructions.
        """
        prompt = f"""
        Analyze this instruction from a child and update the story world state.
        Current Setting: {state.currentSetting}
        Current Facts: {state.continuityFacts}
        Instruction: "{instruction}"
        
        Return JSON with:
        "newSetting": (string, update if changed),
        "newTone": (string, update if changed),
        "addedFacts": (list of new facts learned),
        "removedFacts": (list of facts that are no longer true)
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = self._parse_json(response.text, {})
            
            if data.get("newSetting"):
                state.currentSetting = data["newSetting"]
                plan.currentSetting = data["newSetting"]
            if data.get("newTone"):
                state.narrativeTone = data["newTone"]
                plan.narrativeTone = data["newTone"]
            
            for fact in data.get("addedFacts", []):
                if fact not in state.continuityFacts:
                    state.continuityFacts.append(fact)
            for fact in data.get("removedFacts", []):
                if fact in state.continuityFacts:
                    state.continuityFacts.remove(fact)
        except Exception as e:
            print(f"Error updating narrative: {e}")
    async def generate_movie_plan(self, state: StoryState) -> MoviePlan:
        """
        Creates a 4-shot cinematic movie plan based on the story session.
        """
        history_summary = "\n".join([f"- {b.sceneTitle}: {b.narration}" for b in state.history])
        
        prompt = f"""
        You are a film director for children's animated movies.
        Character: {state.characterProfile.name} ({state.characterProfile.description})
        World: {state.currentSetting}
        Story so far:
        {history_summary}

        Create a 4-shot animated movie plan (Intro, Adventure, Climax, Ending).
        For each shot, provide:
        - "id": unique string
        - "type": one of ['intro', 'adventure', 'climax', 'ending']
        - "narration": short dialogue or narration
        - "bgPrompt": descriptive prompt for the background art (Imagen 3)
        - "motionDirection": one of ['zoom-in', 'zoom-out', 'pan-left', 'pan-right']

        Return JSON with a "shots" list.
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            data = self._parse_json(response.text, {})
            
            shots = []
            for s in data.get("shots", []):
                shots.append(ShotPlan(
                    id=str(uuid4()),
                    type=s.get("type", "adventure"),
                    bgImageUrl="", # To be filled
                    narration=s.get("narration", "The story continues..."),
                    motionDirection=s.get("motionDirection", "zoom-in"),
                    bgPrompt=s.get("bgPrompt", "a beautiful background")
                ))
            return MoviePlan(shots=shots)
        except Exception as e:
            print(f"Error generating movie plan: {e}")
            return MoviePlan(shots=[])
