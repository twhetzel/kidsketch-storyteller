import asyncio
import os
from google.cloud import aiplatform
from vertexai.preview.vision_models import ImageGenerationModel

class ImageGenService:
    def __init__(self, project_id: str, location: str = "us-central1"):
        aiplatform.init(project=project_id, location=location)
        self.model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-001")

    async def generate_image(self, prompt: str, output_path: str) -> str:
        """
        Generates a high-quality illustration using Imagen 3.
        Includes a fallback for quota limits or other errors.
        """
        try:
            # Offload blocking CPU/Network call to a thread
            response = await asyncio.to_thread(
                self.model.generate_images,
                prompt=prompt,
                number_of_images=1,
                language="en",
                aspect_ratio="1:1"
            )
            
            if response.images:
                # Also offload the blocking file write
                await asyncio.to_thread(
                    response.images[0].save,
                    output_path, 
                    include_generation_parameters=False
                )
                return output_path
        except Exception as e:
            print(f"Image Generation failed: {e}")
            # For hackathon, we could return a placeholder or just an empty string
            # to let the narration proceed without the image being the point of failure.
            return ""
        return ""
