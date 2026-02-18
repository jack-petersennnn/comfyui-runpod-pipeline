# ComfyUI RunPod Pipeline

Production-ready ComfyUI deployment on RunPod Serverless for real estate marketing video pipelines. Provides API endpoints for FLUX image generation and face swap operations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Application                      │
│               (Storyboard App / Orchestrator)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    RunPod Serverless API                      │
│                  POST /runsync | /run                         │
│                  GET  /status/{job_id}                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Serverless Handler                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Workflow    │  │   ComfyUI    │  │   Result Upload   │  │
│  │  Injection   │──▶│   Engine     │──▶│   (S3/R2)        │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│                                                              │
│  Loaded Models:                                              │
│  ├── FLUX.1-dev (text-to-image)                             │
│  ├── Kontext Pro (image editing)                            │
│  ├── ReActor (face swap)                                    │
│  └── IPAdapter (style transfer)                             │
└─────────────────────────────────────────────────────────────┘
```

## Endpoints

### Image Generation
Generates real estate scene images from text prompts using FLUX.

**Input:**
```json
{
  "input": {
    "workflow_type": "image_gen",
    "prompt": "Modern luxury kitchen with marble countertops, natural lighting, 8K",
    "negative_prompt": "blurry, low quality, watermark",
    "width": 1280,
    "height": 720,
    "seed": 42,
    "steps": 25,
    "cfg_scale": 7.5
  }
}
```

### Face Swap
Swaps a reference face onto a generated agent/presenter image using ReActor.

**Input:**
```json
{
  "input": {
    "workflow_type": "face_swap",
    "source_image": "https://storage.example.com/agent-photo.jpg",
    "target_image": "https://storage.example.com/generated-scene.png",
    "face_index": 0,
    "restore_face": true
  }
}
```

## Project Structure

```
├── Dockerfile              # RunPod-optimized container
├── src/
│   ├── handler.py          # RunPod serverless handler
│   ├── comfyui_client.py   # ComfyUI WebSocket API client
│   ├── workflow_loader.py  # Workflow template injection
│   └── storage.py          # S3-compatible result upload
├── workflows/
│   ├── flux_image_gen.json # FLUX text-to-image workflow
│   └── face_swap.json      # ReActor face swap workflow
└── scripts/
    ├── deploy.sh           # RunPod deployment script
    └── test_endpoint.py    # Endpoint smoke test
```

## Deployment

### Prerequisites
- RunPod account with API key
- S3-compatible storage (AWS S3, Cloudflare R2, or RunPod storage)

### 1. Build and Push Container

```bash
docker build -t your-registry/comfyui-runpod:latest .
docker push your-registry/comfyui-runpod:latest
```

### 2. Deploy to RunPod

```bash
export RUNPOD_API_KEY="your-key"
export S3_BUCKET="your-bucket"
export S3_ACCESS_KEY="your-access-key"
export S3_SECRET_KEY="your-secret-key"
export S3_ENDPOINT="https://your-endpoint.com"

./scripts/deploy.sh
```

### 3. Test

```bash
python scripts/test_endpoint.py --endpoint-id your-endpoint-id --api-key your-key
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `RUNPOD_API_KEY` | RunPod API authentication | Yes |
| `S3_BUCKET` | Output storage bucket | Yes |
| `S3_ACCESS_KEY` | S3 access key | Yes |
| `S3_SECRET_KEY` | S3 secret key | Yes |
| `S3_ENDPOINT` | S3 endpoint URL | Yes |
| `S3_REGION` | S3 region | No (default: `auto`) |
| `COMFYUI_PORT` | ComfyUI internal port | No (default: `8188`) |

## Model Setup

Models are baked into the Docker image at build time. To customize:

1. Edit `Dockerfile` model download section
2. Add model files to appropriate ComfyUI directories
3. Update workflow JSONs to reference new model filenames

## License

MIT
