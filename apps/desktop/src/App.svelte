<!-- apps/desktop/src/App.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = 'http://127.0.0.1:8000/api/v1';

  // Navigation State
  let currentTab: 'chat' | 'knowledge' | 'media' | 'tasks' | 'settings' = 'chat';
  let token = '';
  let connectionStatus = 'Connecting...';

  // Model & Supervisor State
  let registeredModels: any[] = [];
  let activeModelId: string = '';
  let selectedDropdownModelId: string = '';
  let isSwitchingModel = false;
  let supervisorStatus: any = null;

  // Model Scanner State (Settings)
  let customScanPaths: string = '';
  let scannedModelsList: any[] = [];
  let isScanning = false;

  // Chat & Messaging State
  let messages: { role: string; content: string; image_paths?: string[] }[] = [];
  let promptText = '';
  let isStreaming = false;
  let attachedFiles: { name: string; path: string; type: string }[] = [];
  let knowledgeBases: any[] = [];
  let selectedKbId: string = '';

  // Multimodal Voice & Audio State
  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let voiceReplyEnabled = false;
  let activeAudioUrl: string | null = null;
  let audioElement: HTMLAudioElement;

  // Media Studio State (ComfyUI & Kokoro)
  let imagePrompt = '';
  let imageNegativePrompt = 'ugly, blurry, distorted, bad anatomy';
  let selectedCheckpoint = 'sd_xl_turbo_1.0_fp16.safetensors';
  let ttsText = '';
  let selectedVoice = 'af_heart';
  let mediaGallery: any[] = [];

  // Task Queue State
  let tasks: any[] = [];

  // -------------------------------------------------------------
  // Lifecycle & Health Initialization
  // -------------------------------------------------------------
  async function loadInitialData() {
    // Attempt Tauri native token handshake first
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const nativeToken = await invoke<string>('get_session_token');
      if (nativeToken) token = nativeToken;
    } catch {}

    await checkBackend();

    if (token) {
      await refreshAllData();
    }
  }

  async function checkBackend() {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/health');
      if (res.ok) {
        connectionStatus = 'Backend Connected';
      } else {
        connectionStatus = 'Backend Offline';
      }
    } catch {
      connectionStatus = 'Backend Offline';
    }
  }

  async function refreshAllData() {
    await Promise.all([
      loadSupervisorStatus(),
      loadRegisteredModels(),
      loadSavedDirectories(),
      loadKnowledgeBases(),
      loadTasks(),
      loadGallery(),
    ]);
  }

  // -------------------------------------------------------------
  // Model Supervisor & Scanner Functions
  // -------------------------------------------------------------
  async function loadSupervisorStatus() {
    try {
      const res = await fetch(`${API_BASE}/models/status`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        supervisorStatus = await res.json();
        activeModelId = supervisorStatus.active_model_id || '';
        if (!selectedDropdownModelId && activeModelId) {
          selectedDropdownModelId = activeModelId;
        }
      }
    } catch {}
  }

  async function loadRegisteredModels() {
    try {
      const res = await fetch(`${API_BASE}/models`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        registeredModels = await res.json();
      }
    } catch {}
  }

  async function applyModelSwitch() {
    if (!selectedDropdownModelId || selectedDropdownModelId === activeModelId || isSwitchingModel) return;

    isSwitchingModel = true;
    try {
      const res = await fetch(`${API_BASE}/models/${selectedDropdownModelId}/load`, {
        method: 'POST',
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        await loadSupervisorStatus();
        alert('Model successfully loaded and ready for inference!');
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Failed loading model: ${err.detail || 'Unknown error'}`);
      }
    } catch (e: any) {
      alert(`Network error: ${e.message}`);
    } finally {
      isSwitchingModel = false;
    }
  }

  async function loadSavedDirectories() {
    try {
      const res = await fetch(`${API_BASE}/models/directories`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        const dirs = await res.json();
        customScanPaths = dirs.join('\n');
      }
    } catch {}
  }

  async function triggerScan() {
    isScanning = true;
    const pathsArray = customScanPaths.split('\n').map((p) => p.trim()).filter(Boolean);

    try {
      await fetch(`${API_BASE}/models/directories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ directories: pathsArray }),
      });

      const res = await fetch(`${API_BASE}/models/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ paths: pathsArray }),
      });
      if (res.ok) {
        const data = await res.json();
        scannedModelsList = data.models;
      }
    } catch (e: any) {
      alert(`Scan failed: ${e.message}`);
    } finally {
      isScanning = false;
    }
  }

  async function registerScannedModel(item: any) {
    try {
      const res = await fetch(`${API_BASE}/models/register-scanned`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({
          display_name: item.display_name,
          file_path: item.file_path,
          mmproj_path: item.mmproj_path,
          context_length: 4096,
          vision_supported: item.vision_supported,
          is_default: false,
        }),
      });
      if (res.ok) {
        await loadRegisteredModels();
        alert(`Registered '${item.display_name}'!`);
      }
    } catch (e: any) {
      alert(`Registration failed: ${e.message}`);
    }
  }

  // -------------------------------------------------------------
  // Push-to-Talk Audio & File Attachments
  // -------------------------------------------------------------
  async function toggleRecording() {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  }

  async function startRecording() {
    audioChunks = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        await sendAudioForTranscription(audioBlob);
        stream.getTracks().forEach((track) => track.stop());
      };
      mediaRecorder.start();
      isRecording = true;
    } catch (err: any) {
      alert(`Microphone access error: ${err.message}`);
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
    }
  }

  async function sendAudioForTranscription(blob: Blob) {
    const formData = new FormData();
    formData.append('file', blob, 'mic.webm');
    try {
      const res = await fetch(`${API_BASE}/media/audio/transcribe-direct`, {
        method: 'POST',
        headers: { 'X-AIWA-Token': token },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.text) {
          promptText = promptText ? `${promptText} ${data.text}` : data.text;
        }
      }
    } catch (e) {
      console.error('Transcription error:', e);
    }
  }

  async function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    for (const file of Array.from(input.files)) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`${API_BASE}/files/upload`, {
          method: 'POST',
          headers: { 'X-AIWA-Token': token },
          body: formData,
        });

        if (res.ok) {
          const data = await res.json();
          attachedFiles = [
            ...attachedFiles,
            { name: data.file_name, path: data.file_path, type: data.mime_type },
          ];
        }
      } catch (e) {
        console.error('Upload error:', e);
      }
    }
  }

  function removeAttachment(index: number) {
    attachedFiles = attachedFiles.filter((_, i) => i !== index);
  }

  // -------------------------------------------------------------
  // Chat Completion & Streaming Pipeline
  // -------------------------------------------------------------
  async function sendMessage() {
    if ((!promptText.trim() && attachedFiles.length === 0) || isStreaming) return;

    const currentImages = attachedFiles
      .filter((f) => f.type.startsWith('image/'))
      .map((f) => f.path);

    const userMessage = { role: 'user', content: promptText, image_paths: currentImages };
    messages = [...messages, userMessage];
    promptText = '';
    attachedFiles = [];
    isStreaming = true;

    const assistantIndex = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];
    let assistantAccumulated = '';

    try {
      const response = await fetch(`${API_BASE}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-AIWA-Token': token,
        },
        body: JSON.stringify({
          knowledge_base_id: selectedKbId || null,
          messages: messages.slice(0, -1),
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        const msg = errData.detail || `Server error (HTTP ${response.status})`;
        messages[assistantIndex].content = `⚠️ Error: ${msg}`;
        messages = [...messages];
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());
              if (data.error) {
                messages[assistantIndex].content = `⚠️ ${data.error}`;
                messages = [...messages];
              }
              if (data.text) {
                assistantAccumulated += data.text;
                messages[assistantIndex].content += data.text;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }

      if (voiceReplyEnabled && assistantAccumulated) {
        await playVoiceReply(assistantAccumulated);
      }
    } catch (err: any) {
      messages[assistantIndex].content = `⚠️ Network Error: ${err.message || 'Connection failed'}`;
      messages = [...messages];
    } finally {
      isStreaming = false;
    }
  }

  async function playVoiceReply(text: string) {
    try {
      const res = await fetch(`${API_BASE}/media/audio/speech-direct`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-AIWA-Token': token,
        },
        body: JSON.stringify({ text: text.slice(0, 500), voice: selectedVoice }),
      });

      if (res.ok) {
        const blob = await res.blob();
        if (activeAudioUrl) URL.revokeObjectURL(activeAudioUrl);
        activeAudioUrl = URL.createObjectURL(blob);
        if (audioElement) {
          audioElement.src = activeAudioUrl;
          audioElement.play();
        }
      }
    } catch (e) {
      console.error('Failed playing voice reply:', e);
    }
  }

  // -------------------------------------------------------------
  // Knowledge Base, Media Studio & Tasks
  // -------------------------------------------------------------
  async function loadKnowledgeBases() {
    try {
      const res = await fetch(`${API_BASE}/knowledge-bases`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) knowledgeBases = await res.json();
    } catch {}
  }

  async function loadTasks() {
    try {
      const res = await fetch(`${API_BASE}/tasks`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) tasks = await res.json();
    } catch {}
  }

  async function loadGallery() {
    try {
      const res = await fetch(`${API_BASE}/media/gallery`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) mediaGallery = await res.json();
    } catch {}
  }

  async function triggerImageGen() {
    if (!imagePrompt.trim()) return;
    try {
      await fetch(`${API_BASE}/media/images/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({
          prompt: imagePrompt,
          negative_prompt: imageNegativePrompt,
          checkpoint: selectedCheckpoint,
          width: 512,
          height: 512,
          steps: 4,
        }),
      });
      imagePrompt = '';
      currentTab = 'tasks';
      loadTasks();
    } catch {}
  }

  async function triggerTTS() {
    if (!ttsText.trim()) return;
    try {
      await fetch(`${API_BASE}/media/audio/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ text: ttsText, voice: selectedVoice }),
      });
      ttsText = '';
      currentTab = 'tasks';
      loadTasks();
    } catch {}
  }

  // -------------------------------------------------------------
  // Polling Loop
  // -------------------------------------------------------------
  onMount(() => {
    loadInitialData();
    const interval = setInterval(() => {
      checkBackend();
      if (token) {
        if (currentTab === 'tasks') loadTasks();
        if (currentTab === 'media') loadGallery();
        loadSupervisorStatus();
      }
    }, 3500);
    return () => clearInterval(interval);
  });
</script>

<!-- Audio Tag for Voice Replies -->
<audio bind:this={audioElement} class="hidden"></audio>

<div class="flex h-screen bg-slate-950 text-slate-100 font-sans select-none overflow-hidden">
  <!-- Left Navigation Icon Bar -->
  <nav class="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 space-y-6 z-20">
    <div class="h-10 w-10 bg-indigo-600 rounded-xl flex items-center justify-center font-bold text-lg text-white shadow-lg">
      A
    </div>

    <div class="flex flex-col space-y-4 w-full px-2">
      <button
        on:click={() => (currentTab = 'chat')}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'chat' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="AI Chat"
      >
        💬
      </button>

      <button
        on:click={() => { currentTab = 'knowledge'; loadKnowledgeBases(); }}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'knowledge' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Knowledge Base (RAG)"
      >
        📚
      </button>

      <button
        on:click={() => { currentTab = 'media'; loadGallery(); }}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'media' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Media Studio"
      >
        🎨
      </button>

      <button
        on:click={() => { currentTab = 'tasks'; loadTasks(); }}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'tasks' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Task Dashboard"
      >
        ⚡
      </button>

      <button
        on:click={() => { currentTab = 'settings'; loadSupervisorStatus(); loadSavedDirectories(); }}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'settings' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Settings & Model Scanner"
      >
        ⚙️
      </button>
    </div>
  </nav>

  <!-- Main Viewports -->
  <div class="flex-1 flex overflow-hidden">
    {#if currentTab === 'chat'}
      <!-- ---------------- CHAT VIEWPORT ---------------- -->
      <div class="flex-1 flex flex-col bg-slate-900">
        <!-- Top Chat Header -->
        <header class="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/80">
          <div class="flex items-center gap-3">
            <span class="font-bold text-indigo-400 text-sm">AIWA Chat</span>
            <span class={`h-2.5 w-2.5 rounded-full ${supervisorStatus?.state === 'Ready' ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`}></span>
            <span class="text-xs text-slate-400">
              {supervisorStatus?.state === 'Ready' ? (supervisorStatus.active_model_name || 'Ready') : 'Model Loading/Unloaded'}
            </span>
          </div>

          <!-- Controls: Model Switcher & Knowledge Base Selector -->
          <div class="flex items-center gap-3">
            <!-- RAG Selector -->
            <div class="flex items-center gap-1.5">
              <label for="kb-select" class="text-xs text-slate-400">KB:</label>
              <select
                id="kb-select"
                bind:value={selectedKbId}
                class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="">None (Standard)</option>
                {#each knowledgeBases as kb}
                  <option value={kb.id}>{kb.name}</option>
                {/each}
              </select>
            </div>

            <!-- Model Switcher Dropdown & Apply Button -->
            <div class="flex items-center gap-1.5">
              <label for="model-select" class="text-xs text-slate-400">Model:</label>
              <select
                id="model-select"
                bind:value={selectedDropdownModelId}
                class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                {#each registeredModels as m}
                  <option value={m.id}>
                    {m.display_name} {m.vision_supported ? '👁️' : ''} {m.id === activeModelId ? '●' : ''}
                  </option>
                {/each}
              </select>

              {#if selectedDropdownModelId && selectedDropdownModelId !== activeModelId}
                <button
                  on:click={applyModelSwitch}
                  disabled={isSwitchingModel}
                  class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded transition animate-pulse"
                >
                  {isSwitchingModel ? 'Loading...' : 'Apply Switch'}
                </button>
              {/if}
            </div>

            <!-- Voice Reply Toggle -->
            <div class="flex items-center gap-1.5 border-l border-slate-800 pl-3">
              <label for="voice-toggle" class="text-xs text-slate-400 cursor-pointer select-none">Voice</label>
              <input
                id="voice-toggle"
                type="checkbox"
                bind:checked={voiceReplyEnabled}
                class="h-3.5 w-3.5 accent-indigo-600 rounded cursor-pointer"
              />
            </div>
          </div>
        </header>

        <!-- Message History -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          {#if messages.length === 0}
            <div class="h-full flex flex-col items-center justify-center text-slate-500 space-y-2">
              <p class="text-base font-medium text-slate-400">Multimodal AI Workspace Ready</p>
              <p class="text-xs text-slate-500">Dictate via microphone, attach images for vision analysis, or type your query.</p>
            </div>
          {:else}
            {#each messages as msg}
              <div class={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div class={`max-w-2xl px-4 py-3 rounded-2xl text-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'}`}>
                  {#if msg.image_paths && msg.image_paths.length > 0}
                    <div class="mb-2 text-xs text-indigo-200 flex items-center gap-1 font-mono">
                      🖼️ Attached {msg.image_paths.length} image(s)
                    </div>
                  {/if}
                  <p class="whitespace-pre-wrap select-text">{msg.content}</p>
                </div>
              </div>
            {/each}
          {/if}
        </div>

        <!-- Multimodal Input Bar -->
        <div class="p-4 border-t border-slate-800 bg-slate-900/90">
          {#if attachedFiles.length > 0}
            <div class="flex flex-wrap gap-2 mb-2">
              {#each attachedFiles as file, index}
                <div class="flex items-center gap-1.5 bg-slate-800 border border-slate-700 px-2.5 py-1 rounded-md text-xs text-slate-300">
                  <span>{file.type.startsWith('image/') ? '🖼️' : '📄'}</span>
                  <span class="truncate max-w-[200px]">{file.name}</span>
                  <button on:click={() => removeAttachment(index)} class="text-slate-400 hover:text-rose-400 ml-1">✕</button>
                </div>
              {/each}
            </div>
          {/if}

          <div class="flex items-center gap-2">
            <!-- File Picker -->
            <label
              class="p-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg cursor-pointer transition"
              title="Attach Image or PDF"
            >
              📎
              <input
                type="file"
                accept="image/*,application/pdf"
                multiple
                on:change={handleFileUpload}
                class="hidden"
              />
            </label>

            <!-- Push-to-Talk Mic -->
            <button
              type="button"
              on:click={toggleRecording}
              class={`p-2.5 rounded-lg border transition flex items-center justify-center ${
                isRecording
                  ? 'bg-rose-600 border-rose-500 text-white animate-pulse'
                  : 'bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300'
              }`}
              title={isRecording ? 'Click to Stop Recording' : 'Push-to-Talk'}
            >
              🎤
            </button>

            <!-- Main Input -->
            <input
              type="text"
              bind:value={promptText}
              on:keydown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder={isRecording ? 'Listening to voice...' : 'Ask question, analyze image, or speak...'}
              disabled={isStreaming}
              class="flex-1 bg-slate-800 text-slate-100 rounded-lg px-4 py-2.5 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500 select-text"
            />

            <!-- Send Button -->
            <button
              on:click={sendMessage}
              disabled={isStreaming || (!promptText.trim() && attachedFiles.length === 0)}
              class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition"
            >
              Send
            </button>
          </div>
        </div>
      </div>

    {:else if currentTab === 'knowledge'}
      <!-- ---------------- KNOWLEDGE BASE VIEWPORT ---------------- -->
      <div class="flex-1 p-8 overflow-y-auto space-y-6">
        <div>
          <h2 class="text-xl font-bold text-slate-100">Knowledge Bases (LanceDB RAG)</h2>
          <p class="text-xs text-slate-400 mt-1">Embedded vector search running ONNX embeddings on CPU.</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          {#each knowledgeBases as kb}
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-2">
              <h3 class="font-bold text-indigo-400">{kb.name}</h3>
              <p class="text-xs text-slate-400">{kb.description || 'No description provided.'}</p>
              <div class="text-[11px] font-mono text-slate-500 pt-2 border-t border-slate-800">Model: {kb.embedding_model}</div>
            </div>
          {/each}
        </div>
      </div>

    {:else if currentTab === 'media'}
      <!-- ---------------- MEDIA STUDIO VIEWPORT ---------------- -->
      <div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl">
        <div>
          <h2 class="text-xl font-bold text-slate-100">Media Studio</h2>
          <p class="text-xs text-slate-400 mt-1">Image generation via ComfyUI and voice synthesis via Kokoro.</p>
        </div>

        <!-- ComfyUI Image Generation -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
          <h3 class="text-sm font-bold text-indigo-400">🎨 Image Generator (ComfyUI)</h3>
          <div class="space-y-3">
            <div>
              <label for="img-prompt-input" class="text-xs text-slate-400 block mb-1">Prompt:</label>
              <input
                id="img-prompt-input"
                type="text"
                bind:value={imagePrompt}
                placeholder="A futuristic cybernetic metropolis in neon rain..."
                class="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2 text-xs focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div class="grid grid-cols-2 gap-4">
              <div>
                <label for="img-neg-input" class="text-xs text-slate-400 block mb-1">Negative Prompt:</label>
                <input
                  id="img-neg-input"
                  type="text"
                  bind:value={imageNegativePrompt}
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
                />
              </div>

              <div>
                <label for="checkpoint-select" class="text-xs text-slate-400 block mb-1">Checkpoint:</label>
                <select
                  id="checkpoint-select"
                  bind:value={selectedCheckpoint}
                  class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none"
                >
                  <option value="sd_xl_turbo_1.0_fp16.safetensors">SDXL-Turbo (Fast 4-step)</option>
                  <option value="DreamShaperXL_Lightning.safetensors">DreamShaper XL Lightning</option>
                  <option value="v1-5-pruned-emaonly.safetensors">SD 1.5 Pruned</option>
                </select>
              </div>
            </div>

            <button
              on:click={triggerImageGen}
              disabled={!imagePrompt.trim()}
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded-lg transition"
            >
              Generate Image (Safe VRAM Swap)
            </button>
          </div>
        </div>

        <!-- Kokoro Audio Synthesis -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
          <h3 class="text-sm font-bold text-indigo-400">🔊 Text-to-Speech (Kokoro)</h3>
          <div class="space-y-3">
            <div>
              <label for="tts-text-input" class="text-xs text-slate-400 block mb-1">Text:</label>
              <textarea
                id="tts-text-input"
                rows="2"
                bind:value={ttsText}
                placeholder="Enter text to synthesize into spoken audio..."
                class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs focus:outline-none focus:border-indigo-500"
              ></textarea>
            </div>

            <div class="flex items-center gap-3">
              <select
                bind:value={selectedVoice}
                class="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none"
              >
                <option value="af_heart">Heart (US Warm Female)</option>
                <option value="am_adam">Adam (US Deep Male)</option>
                <option value="bf_emma">Emma (UK Professional Female)</option>
              </select>

              <button
                on:click={triggerTTS}
                disabled={!ttsText.trim()}
                class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded-lg transition"
              >
                Synthesize Speech
              </button>
            </div>
          </div>
        </div>
      </div>

    {:else if currentTab === 'tasks'}
      <!-- ---------------- TASK DASHBOARD VIEWPORT ---------------- -->
      <div class="flex-1 p-8 overflow-y-auto">
        <h2 class="text-xl font-bold mb-6 text-slate-100">Task Queue Operations</h2>
        <table class="w-full text-left text-sm border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 text-xs">
              <th class="py-2.5">Task Type</th>
              <th class="py-2.5">Status</th>
              <th class="py-2.5">Progress</th>
              <th class="py-2.5">Created At</th>
            </tr>
          </thead>
          <tbody>
            {#each tasks as t}
              <tr class="border-b border-slate-800/60 hover:bg-slate-900/50">
                <td class="py-3 font-mono text-xs text-indigo-300">{t.task_type}</td>
                <td class="py-3">
                  <span class={`px-2 py-0.5 rounded text-[11px] font-semibold ${t.status === 'completed' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : t.status === 'running' ? 'bg-amber-950 text-amber-400 border border-amber-800 animate-pulse' : 'bg-slate-800 text-slate-300'}`}>
                    {t.status}
                  </span>
                </td>
                <td class="py-3 text-xs text-slate-400">{t.progress_percent}%</td>
                <td class="py-3 text-xs text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

    {:else if currentTab === 'settings'}
      <!-- ---------------- SETTINGS & MODEL SCANNER VIEWPORT ---------------- -->
      <div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl">
        <div>
          <h2 class="text-xl font-bold text-slate-100">Workstation Settings & Model Catalog</h2>
          <p class="text-xs text-slate-400 mt-1">Configure multi-drive search folders, observe VRAM arbitration, and manage credentials.</p>
        </div>

        <!-- Hardware & VRAM Status -->
        {#if supervisorStatus}
          <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-2">
            <h3 class="text-sm font-semibold text-slate-300">GPU Resource Arbiter (80% Safety Ceiling)</h3>
            <div class="grid grid-cols-3 gap-4 pt-2 font-mono text-xs">
              <div class="bg-slate-800/60 p-3 rounded-lg border border-slate-700/50">
                <span class="text-slate-500 block text-[10px]">TOTAL VRAM</span>
                <span class="text-slate-200 text-sm font-bold">{supervisorStatus.vram?.total_mb} MB</span>
              </div>
              <div class="bg-slate-800/60 p-3 rounded-lg border border-slate-700/50">
                <span class="text-slate-500 block text-[10px]">80% CEILING BUDGET</span>
                <span class="text-indigo-400 text-sm font-bold">{supervisorStatus.vram?.allowed_ceiling_mb} MB</span>
              </div>
              <div class="bg-slate-800/60 p-3 rounded-lg border border-slate-700/50">
                <span class="text-slate-500 block text-[10px]">USABLE FREE VRAM</span>
                <span class="text-emerald-400 text-sm font-bold">{supervisorStatus.vram?.effective_free_mb} MB</span>
              </div>
            </div>
          </div>
        {/if}

        <!-- Multi-Directory GGUF Scanner -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
          <label for="custom-dirs-input" class="text-sm font-semibold text-slate-300 block">Model Search Directories (one per line):</label>
          <textarea
            id="custom-dirs-input"
            rows="3"
            bind:value={customScanPaths}
            placeholder="/run/media/alpha/.../models&#10;/home/.../weights"
            class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
          ></textarea>

          <button
            on:click={triggerScan}
            disabled={isScanning}
            class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded-lg transition"
          >
            {isScanning ? 'Scanning Drives...' : '🔍 Scan Directories for GGUF Models'}
          </button>
        </div>

        <!-- Discovered Models List -->
        {#if scannedModelsList.length > 0}
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-slate-300">Discovered Models ({scannedModelsList.length}):</h3>
            <div class="grid grid-cols-1 gap-2.5">
              {#each scannedModelsList as model}
                <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex items-center justify-between">
                  <div>
                    <div class="flex items-center gap-2">
                      <span class="font-bold text-sm text-slate-200">{model.display_name}</span>
                      {#if model.vision_supported}
                        <span class="px-2 py-0.5 bg-indigo-950 border border-indigo-700 text-indigo-300 rounded text-[10px] font-semibold">👁️ Vision Ready</span>
                      {/if}
                      {#if model.quantization}
                        <span class="px-2 py-0.5 bg-slate-800 border border-slate-700 text-slate-300 rounded text-[10px] font-mono">{model.quantization}</span>
                      {/if}
                    </div>
                    <p class="text-xs text-slate-500 font-mono mt-0.5 truncate max-w-xl">{model.file_path}</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">Size: {model.file_size_gb} GB</p>
                  </div>

                  <button
                    on:click={() => registerScannedModel(model)}
                    class="px-3.5 py-1.5 bg-slate-800 hover:bg-indigo-600 border border-slate-700 hover:border-indigo-500 text-xs font-medium rounded-lg transition"
                  >
                    + Register Model
                  </button>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Session Token Storage -->
        <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-3">
          <label for="token-storage-input" class="text-sm font-semibold text-slate-300 block">Session Token (data/.aiwa_session_token)</label>
          <input
            id="token-storage-input"
            type="password"
            bind:value={token}
            placeholder="Paste session token..."
            class="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>
    {/if}
  </div>
</div>
