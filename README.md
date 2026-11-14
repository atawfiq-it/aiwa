<div align="center">

# 🌿 AI Workspace App (AIWA)
### Local Multimodal AI Workstation

**Say *"Yes"* to 100% private, sovereign, multimodal AI on consumer workstation hardware.**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tauri v2](https://img.shields.io/badge/Desktop-Tauri_v2-24C8DB?style=flat&logo=tauri&logoColor=white)](https://tauri.app/)
[![Svelte](https://img.shields.io/badge/Frontend-Svelte-FF3E00?style=flat&logo=svelte&logoColor=white)](https://svelte.dev/)
[![LLM Runtime](https://img.shields.io/badge/LLM-llama.cpp-yellow?style=flat)](https://github.com/ggerganov/llama.cpp)
[![Package Manager](https://img.shields.io/badge/Packaging-uv-blueviolet?style=flat)](https://github.com/astral-sh/uv)
[![Linux Packaging](https://img.shields.io/badge/Bundle-AppImage_%7C_Debian-blue?style=flat&logo=linux)](https://github.com/)

[Features](#-key-features) • [The Story of "Aiwa"](#-what-does-aiwa-mean) • [Recommended Models](#-recommended-models) • [Quick Start](#-quick-start-installation) • [Workstation Architecture](#-architecture) • [Contributing & Connect](#-connect--contribute)

</div>

---

## 💡 What Does "Aiwa" Mean?

> **"AI Workspace App (Aiwa)" (أيوه)** is the vibrant, everyday Arabic slang for **"YES!"** — an energetic affirmation of capability and agreement.

When asked:
* *Can you run 7B vision-language models, fast image diffusion, and neural voice synthesis entirely on local hardware?*
* *Can an 8GB to 12GB consumer GPU handle visual reasoning, text generation, and media without cloud subscriptions or telemetry?*
* *Can developer workflows, document intelligence, and autonomous code execution remain 100% private and offline?*

The answer is **AIWA! (أيوه)**.

---

## 👨‍💻 About the Project & Creator

Hello! I built **AIWA** out of a passion for local-first computing, private AI infrastructure, and responsive developer tooling.

While cloud AI services offer convenient APIs, they lock users into recurring costs, unpredictable latency, privacy compromises, and walled gardens. Most existing local AI interfaces either act as simple text wrappers around Ollama or require managing a disjointed collection of separate applications (one for LLM chat, one for ComfyUI, another for Whisper, and terminal scripts for RAG).

**AIWA** unifies these capabilities into an integrated, decoupled workstation:
* A high-performance **FastAPI daemon** orchestrated by a central **VRAM Arbiter**.
* A sleek, lightweight **Tauri desktop shell** built with Svelte and Tailwind CSS.
* **Three focused, conflict-free studios** (Text & Vision, Image Diffusion, and Voice) that maximize GPU efficiency without process clashes.

---
## ⚖️ Responsible Use & Ethical Disclaimer

**AIWA** is created to foster local AI sovereignty, privacy-conscious research, and productive developer automation. Because all model inference, diffusion, and code execution run 100% locally on your personal hardware without centralized telemetry or cloud filters, **users bear sole responsibility for the prompts, media, code, and content generated using this platform.**

### Acceptable & Lawful Use Guidelines:
By using this software, you agree to use AIWA exclusively for lawful, ethical, and non-harmful purposes, including agreeing NOT to use AIWA to:
* **Generate Malicious Code**: Create malware, exploits, keyloggers, or automate cyberattacks inside or outside the Python sandbox.
* **Produce Harmful or Non-Consensual Imagery**: Render deceptive deepfakes, non-consensual explicit material, defamatory visuals, or imagery that violates applicable laws.
* **Disinformation & Impersonation**: Generate deceptive voice clones or automated propaganda designed to deceive or harass individuals or organizations.
* **Violate Third-Party Licenses**: Generate or process content in violation of original model licenses (e.g., Qwen, SDXL, or Kokoro community licenses).

### Limitation of Liability:
The creator and contributors of AIWA provide this software on an *"as is"* basis without warranties of any kind. Under no circumstances shall the author be held liable for any damages, legal claims, or misuse arising from local model outputs or user-initiated actions.

---
## 🚀 Key Features

### 1. 💬 Dedicated Text & Vision Studio
* **Powered by `llama.cpp`**: Single, standardized C++ inference runtime.
* **Multimodal Visual Analysis**: Attach `.png`, `.jpg`, or `.pdf` files directly for document reading, UI inspection, and visual reasoning.
* **4,096+ Token Context Window**: Ample breathing room for high-resolution visual patch tokens and multi-turn conversations without premature truncation.
* **WhatsApp-Style Character Personas**: Switch between specialized personas (*Software Architect*, *Creative Storyteller*, *Code Reviewer*, *Research Analyst*, *Executive Brief Writer*) with local disk avatars and distinct cognitive perspectives.
* **In-Chat Message Management**: Edit (✏️) or delete (✕) any prompt or reply directly inside the thread, with one-click Rich Markdown (`.md`) export.
* **Instant Cancellation**: One-click `⏹ Stop` button powered by `AbortController` to halt generation mid-sentence.

### 2. 🎨 Pro Direct-Diffusion Studio
* **Serverless PyTorch FP16 Diffusion**: Direct checkpoint execution via Hugging Face `diffusers` — zero external server daemons or complex node-graph configurations required.
* **Multi-Directory `.safetensors` Discovery**: Automatically scans directories configured in `.env` across all your drives.
* **Gold-Standard Samplers**: Choose between `DPM++ 2M Karras`, `Euler a`, `Euler`, and `DDIM`.
* **Pro Artistic Controls**: Fine-tune sampling steps (up to 50), CFG guidance scales (1.0 to 15.0), aspect ratios, style presets (*Cinematic*, *Photorealistic*, *Anime*, *Digital Art*), deterministic seeds, and batch sizes (1, 2, or 4 images).
* **Safe Local Media Storage**: Full-resolution image canvas with instant download and disk deletion.

### 3. 🎙️ Voice Studio Pro (100% CPU-Bound)
* **Neural Speech Synthesis (Kokoro-82M)**: Natural, human-like voice synthesis with selectable voice profiles (*Heart*, *Adam*, *Emma*) and native speed multipliers (`0.75x` to `1.5x`).
* **Multi-Speaker Podcast Generator**: Import multi-line dialogue CSV files (`speaker,voice,text`) to generate full conversational podcasts with programmatic silence pauses and master `.wav` export.
* **Speech-to-Text (Faster-Whisper)**: Accurate microphone transcription and audio file speech-to-text with one-click synchronized `.SRT` and `.VTT` subtitle generation.
* **Zero VRAM Contention**: Runs exclusively on the CPU using INT8/Float32 compute, leaving 100% of GPU memory for graphics and language models.

### 4. 🤖 Autonomous Agent Studio Pro
* **Visual Reasoning DAG (Directed Acyclic Graph)**: Interactive cognitive timeline rendering step-by-step nodes:
  $$\text{🎯 Goal} \longrightarrow \text{🧠 Strategy} \longrightarrow \text{⚡ Action (Tool Call)} \longrightarrow \text{📦 Sandbox Observation} \longrightarrow \text{📋 Synthesis}$$
* **Human-in-the-Loop (HITL) Breakpoints**: Safely inspects, edits, or rejects Python code before execution in the sandbox.
* **Process-Isolated Execution Sandbox**: Hardened child subprocess environment with strict CPU time caps and virtual memory limits (`resource.setrlimit`).
* **Persistent Task Records**: Auto-saves completed agent audits and benchmark runs with inline title renaming, history reload, and disk workspace cleanup.

### 5. 🛡️ Central Model Supervisor & VRAM Arbiter
* **80% Dynamic GPU Ceiling**: Queries NVIDIA NVML to enforce safety reserves, protecting your desktop display server and preventing Out-Of-Memory (OOM) crashes on 8GB–12GB GPUs.
* **Dynamic Layer Calculator**: Automatically calculates how many model layers safely fit into VRAM, offloading the rest to system RAM.

---

## 🎯 Recommended Models

| Modality | Recommended Model | Format | Context / Profile | Memory Footprint |
| :--- | :--- | :--- | :--- | :--- |
| **Language & Vision** | **`Qwen2.5-VL-7B-Instruct`** *(or upcoming **`Qwen3-VL`**)* | GGUF (`Q4_K_M`) + `mmproj-f16.gguf` | 4,096 tokens (min) | ~4.8 GB VRAM |
| **Image Generation** | **`SDXL-Turbo`** or **`DreamShaper XL Lightning`** | `.safetensors` (FP16) | 512x512 / 1024x1024, 4–25 steps | ~3.8 – 5.5 GB VRAM |
| **Fast Image Gen** | **`Stable Diffusion 1.5 Pruned`** | `.safetensors` (FP16) | 512x512, 20–25 steps (DPM++) | ~2.2 GB VRAM |
| **Speech Output (TTS)** | **`Kokoro-82M`** | PyTorch / ONNX | Multi-voice (`af_heart`, `am_adam`, `bf_emma`) | CPU (~350 MB RAM) |
| **Speech Input (STT)** | **`Faster-Whisper (base.en / small)`** | CTranslate2 INT8 | Sentence timestamps + SRT | CPU (~250 MB RAM) |
| **Local RAG Embeddings** | **`BAAI/bge-small-en-v1.5`** | FastEmbed ONNX | LanceDB Vector Storage | CPU (~120 MB RAM) |

> 🌟 **Recommendation**: For the best multimodal experience, we strongly recommend **`Qwen2.5-VL-7B-Instruct`** (paired with its matching `mmproj` file) or the next-generation **`Qwen3-VL`** upon release. It handles both complex coding/reasoning and visual chart/image analysis in a single runtime.

---

## 🛠️ Architecture

AIWA enforces clean separation between application logic, runtime orchestration, and presentation:

```text
aiwa/
├── apps/
│   └── desktop/               # Tauri v2 Desktop Shell
│       ├── src/               # Svelte + TypeScript + Tailwind CSS Frontend
│       │   ├── components/    # Modular Studios (Chat, Image, Voice, Agent)
│       │   └── lib/           # Stores, API Client, and Types
│       └── src-tauri/         # Rust Desktop Bridge & Lifecycle Manager
│
├── backend/                   # Core Python Engine
│   ├── app/
│   │   ├── api/v1/            # Versioned REST & SSE Endpoints
│   │   ├── core/              # Config, Security Tokens, Logging
│   │   ├── database/          # SQLModel Entities & Engine
│   │   ├── services/          # Domain Services (Chat, Media, Voice, RAG, Agents)
│   │   └── supervisors/       # Model Supervisor & Central VRAM Arbiter
│   ├── migrations/            # Version-controlled Alembic Migrations
│   └── pyproject.toml         # uv-managed reproducible dependencies
│
├── data/                      # 100% Local Application Data (Git-Ignored)
│   ├── database/              # SQLite DB (WAL Mode)
│   ├── models/                # Local GGUF Weights & Projectors
│   ├── uploads/               # User attachments & documents
│   ├── generated/             # Rendered artwork and synthesized audio
│   └── vector_store/          # Embedded LanceDB tables
│
├── services/                  # Standalone External Binaries (llama-server)
└── Justfile                   # Unified developer task runner
```

---

## 📦 Quick Start & Installation

### Prerequisites
* **Operating System**: Linux (Ubuntu 22.04+, Debian, Arch, Fedora) or Windows via WSL2 / native.
* **GPU**: NVIDIA GPU with 8GB+ VRAM recommended (CUDA 12+ drivers installed).
* **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (fast Python package manager).
* **Node.js**: Node 18+ and `npm`.
* **Rust**: `cargo` and `rustc` (required for compiling native Tauri desktop installers).
* **System Audio Libraries**: `libsndfile1` and `ffmpeg` (for Kokoro & Whisper).

```bash
# Ubuntu / Debian system libraries:
sudo apt update && sudo apt install -y libsndfile1 ffmpeg build-essential curl
```

---

### 1. Clone the Repository
```bash
git clone https://github.com/atawfiq-it/aiwa.git
cd aiwa
```

### 2. Install Dependencies (Single Command)
Install backend Python dependencies (locked via `uv`), development hooks, and desktop frontend modules:
```bash
just install
```

### 3. Setup `llama-server`
Download and compile `llama-server` with native CUDA acceleration:
```bash
just install-llama
```

### 4. Configure Environment (`.env`)
Create a `.env` file in the root directory to define your custom model search paths:
```env
# Root .env configuration
ENVIRONMENT=development
MAX_GPU_USAGE_PERCENT=80.0

# Add paths to your existing diffusion models (comma-separated)
DIFFUSION_MODEL_DIRECTORIES="/path/to/your/checkpoints,/path/to/another/folder"
```

### 5. Launch the Workstation!
Run both the FastAPI daemon and the desktop UI with one command:
```bash
just workstation
```
Open **`http://localhost:5173`** in your browser, or interact through the native desktop shell.

---

## 🩺 System Diagnostics (`just doctor`)

Verify your CUDA driver, VRAM arbiter, database, and installed runtimes in 2 seconds:
```bash
just doctor
```

Output:
```text
=== AIWA SYSTEM DIAGNOSTICS ===
Python: 3.11.x
CUDA Available: True
GPU Device: NVIDIA GeForce RTX (8.0 GB)
VRAM Arbiter: {'total_mb': 8192, 'allowed_ceiling_mb': 6553, 'free_mb': ...}
llama-server: FOUND
Database: FOUND (Schema v0.1.0)
================================
```

---

## 📦 Building Native Desktop Installers (.AppImage & .deb)

Package AIWA into standalone, native Linux desktop bundles featuring your system's OS window decorations and an embedded folder-based Python sidecar:

```bash
just package-desktop
```

Generated bundles will be ready in:
* `apps/desktop/src-tauri/target/release/bundle/appimage/AIWA_0.1.0_amd64.AppImage`
* `apps/desktop/src-tauri/target/release/bundle/deb/aiwa_0.1.0_amd64.deb`

---

## 🔒 Security & Data Privacy First

* **Zero External Telemetry**: No prompt, code, document, or audio snippet is ever sent to external cloud APIs by default.
* **Strict Git Shielding**: Pre-commit hooks automatically block any accidental commit of database files (`.db`), session tokens, private uploads, or weights exceeding 10 MB.
* **Local Loopback Security**: The backend daemon binds strictly to `127.0.0.1` protected by ephemeral session tokens.
* **Subprocess Sandboxing**: Agent-executed Python code runs in an isolated temporary environment with hard memory caps (`RLIMIT_AS`) and CPU execution timeouts.

---

## 🤝 Connect & Contribute

AIWA is actively evolving, and contributions from the developer and AI research community are warmly welcomed!

### Roadmap Ahead:
- [ ] Windows native packaging (`.exe` via NSIS & `.msi` via WiX).
- [ ] Visual multi-agent swarm planner and task orchestrator.
- [ ] Web search integration tool for the Research Analyst agent.
- [ ] HuggingFace GGUF one-click in-app downloader polish.

### Ways to Contribute:
1. **Report Bugs & Suggest Features**: Open an [Issue](https://github.com/atawfiq-it/aiwa/issues).
2. **Submit Pull Requests**: Fork the repository, create your feature branch, and submit a PR!
3. **Model Presets**: Share tested prompt templates and parameter profiles for new GGUF / diffusion models.

### Get in Touch:
* **Creator**: Ahmed Tawfiq
* **GitHub**: [@atawfiq-it](https://github.com/atawfiq-it)
* **LinkedIn**: [linkedin.com/in/amtawfiq](https://linkedin.com/in/amtawfiq)
