## KidSketch Storyteller Architecture

This document gives a high-level view of how the KidSketch Storyteller system is structured across client, backend, and Google Cloud Platform services.

### Overview Diagram

```mermaid
flowchart TB
    %% Client
    subgraph Client
        U[Child / Parent\nWeb Browser]
    end

    %% Frontend on Cloud Run
    subgraph FE[Cloud Run - kidsketch-frontend]
        F[Next.js App]
    end

    %% Backend on Cloud Run
    subgraph BE[Cloud Run - kidsketch-backend]
        B[FastAPI Service\n(main.py)]
        SA[StoryAgent\n(primary: Gemini)]
        IMG[ImageGenService\n(optional: Imagen 3)]
        VE[VideoEngine\n(ffmpeg, Pillow)]
        ST[StorageService\n(session state, assets)]
        MM[MultimodalLiveBridge\n(WebSocket to Gemini Live)]
    end

    %% Managed GCP services
    subgraph GCP[Google Cloud Services]
        GCS[(GCS Bucket\nsketches, images,\naudio, movies)]
        VA[Vertex AI\nImagen 3 (fallback)]
        GEM[Gemini API\n(text + vision + Live)]
        SM[Secret Manager\nGEMINI_API_KEY]
    end

    %% Flow: top → bottom
    U --> F
    F -->|REST & WebSocket| B

    %% Backend → Gemini (primary)
    B --> SA
    SA --> GEM

    %% Backend → Imagen (explicit fallback)
    B --> IMG
    IMG -. optional fallback .-> VA

    %% Storage
    B --> ST
    ST --> GCS

    %% Video assembly
    B --> VE
    VE --> ST
    VE --> GCS

    %% Live multimodal
    B --> MM
    MM --> GEM

    %% Config / secrets
    SM --> B
```

### Component Responsibilities

- **Client (`Next.js` UI in browser)**: Allows children and parents to upload sketches, view character profiles, build scene beats, and export the final "living movie".
- **Frontend (`kidsketch-frontend` on Cloud Run)**: Serves the Next.js app and forwards API and WebSocket traffic to the backend using `NEXT_PUBLIC_API_URL`.
- **Backend (`kidsketch-backend` on Cloud Run / FastAPI)**:
  - Exposes REST endpoints for session lifecycle, sketch analysis, beat creation/update, and movie export.
  - Manages in-memory and persisted story state (via `StorageService` and GCS).
  - **Uses Gemini as the primary model** for sketch analysis, story planning, beat generation, and live character conversations (via `StoryAgent` and `MultimodalLiveBridge`).
  - **Optionally calls Imagen 3 as a fallback** via `ImageGenService` only when Gemini does not return an inline image for a beat or character.
  - Assembles the final video from beats using `VideoEngine`, ffmpeg, and TTS output.
- **Google Cloud Storage (GCS)**: Stores user sketches, generated character images, beat images, TTS audio, exported videos, and serialized session state.
- **Vertex AI (Imagen 3)**: Generates character and scene images when not provided inline by Gemini.
- **Gemini API (text, vision, Multimodal Live)**: Powers sketch analysis, story and beat generation, and live interactive character conversations via WebSocket.
- **Secret Manager**: Holds the `GEMINI_API_KEY`, injected into the backend service at runtime without embedding secrets in the image or source.

### Typical Flow

1. **Sketch upload & session init**: The client hits the backend to create a session, then uploads a drawing, which is stored in GCS and analyzed by Gemini to produce a character profile and reference image.
2. **Story beat creation**: For each new beat, the backend uses the current `StoryState` and `StoryPlan` to ask Gemini for the next scene description and (optionally) an inline image, falling back to Imagen 3 as needed, then saves both state and assets to GCS.
3. **Live character conversation**: The client opens a WebSocket to `/ws/live/{session_id}`, and the backend bridges audio/text to Gemini Multimodal Live with a carefully constructed, safe system prompt based on the current character profile and story.
4. **Movie export**: When requested, the backend generates TTS audio for each beat, uses locally cached beat images and audio with `VideoEngine` + ffmpeg to create an animated movie, uploads the final MP4 to GCS, and returns a public URL to the frontend.

