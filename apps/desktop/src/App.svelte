<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = 'http://127.0.0.1:8000/api/v1';

  // Navigation State
  let currentTab: 'chat' | 'knowledge' | 'media' | 'tasks' | 'settings' = 'chat';
  let token = '';
  let connectionStatus = 'Connecting...';

  // Chat & Multimodal State
  let messages: {
    role: string;
    content: string;
    image_paths?: string[];
  }[] = [];
  let promptText = '';
  let isStreaming = false;
  let currentConversationId: string | null = null;
  let knowledgeBases: { id: string; name: string; description?: string; embedding_model: string }[] = [];
  let selectedKbId: string = '';

  // Push-to-Talk & Audio Playback
  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let voiceReplyEnabled = false;
  let audioElement: HTMLAudioElement;
  let activeAudioUrl: string | null = null;

  // File Attachments (Images & PDFs)
  let attachedFiles: { name: string; path: string; type: string }[] = [];

  // Media Studio State
  let imagePrompt = '';
  let ttsText = '';
  let mediaGallery: any[] = [];

  // Tasks & System State
  let tasks: any[] = [];
  let supervisorStatus: any = null;

  // --- Initialization & Health Check ---
  async function loadInitialData() {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const nativeToken = await invoke<string>('get_session_token');
      if (nativeToken) token = nativeToken;
    } catch {}

    try {
      const res = await fetch('http://127.0.0.1:8000/api/v1/health');
      if (res.ok) {
        connectionStatus = 'Backend Connected';
        if (token) {
          refreshAllData();
        }
      } else {
        connectionStatus = 'Backend Offline';
      }
    } catch {
      connectionStatus = 'Backend Offline';
    }
  }

  function refreshAllData() {
    loadKnowledgeBases();
    loadTasks();
    loadGallery();
    loadSupervisor();
  }

  async function loadKnowledgeBases() {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/knowledge-bases`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) knowledgeBases = await res.json();
    } catch {}
  }

  async function loadTasks() {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/tasks`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) tasks = await res.json();
    } catch {}
  }

  async function loadGallery() {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/media/gallery`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) mediaGallery = await res.json();
    } catch {}
  }

  async function loadSupervisor() {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/models/status`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) supervisorStatus = await res.json();
    } catch {}
  }

  // --- Push-to-Talk (Microphone Recording) ---
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
    } catch (err) {
      alert('Microphone access denied or unavailable: ' + err);
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
    formData.append('file', blob, 'recording.webm');

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

  // --- File Uploads (Images & PDFs) ---
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
        console.error('File upload error:', e);
      }
    }
    input.value = '';
  }

  function removeAttachment(index: number) {
    attachedFiles = attachedFiles.filter((_, i) => i !== index);
  }

  // --- Chat Message Sending & Streaming ---
  async function sendMessage() {
    if ((!promptText.trim() && attachedFiles.length === 0) || isStreaming) return;

    const currentImages = attachedFiles
      .filter((f) => f.type.startsWith('image/'))
      .map((f) => f.path);

    const userMessage = {
      role: 'user',
      content: promptText,
      image_paths: currentImages,
    };

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
          conversation_id: currentConversationId,
          knowledge_base_id: selectedKbId || null,
          messages: messages.slice(0, -1),
        }),
      });

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
              if (data.text) {
                assistantAccumulated += data.text;
                messages[assistantIndex].content += data.text;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }

      // Voice Reply: Auto-synthesize and play speech via Kokoro
      if (voiceReplyEnabled && assistantAccumulated) {
        await playVoiceReply(assistantAccumulated);
      }
    } catch {
      messages[assistantIndex].content += '\n[Inference Error]';
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
        body: JSON.stringify({ text: text.slice(0, 500) }),
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

  // --- Media Studio Actions ---
  async function triggerImageGen() {
    if (!imagePrompt.trim()) return;
    try {
      await fetch(`${API_BASE}/media/images/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ prompt: imagePrompt }),
      });
      imagePrompt = '';
      loadTasks();
    } catch {}
  }

  async function triggerTTS() {
    if (!ttsText.trim()) return;
    try {
      await fetch(`${API_BASE}/media/audio/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ text: ttsText }),
      });
      ttsText = '';
      loadTasks();
    } catch {}
  }

  onMount(() => {
    loadInitialData();
    const interval = setInterval(() => {
      if (token) {
        if (currentTab === 'tasks') loadTasks();
        if (currentTab === 'media') loadGallery();
      }
    }, 3000);
    return () => clearInterval(interval);
  });
</script>

<div class="flex h-screen bg-slate-950 text-slate-100 font-sans">
  <!-- Left-Side Navigation Bar -->
  <nav class="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 space-y-6 select-none">
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
        on:click={() => { currentTab = 'settings'; loadSupervisor(); }}
        class={`p-3 rounded-lg flex justify-center transition ${currentTab === 'settings' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Settings & System"
      >
        ⚙️
      </button>
    </div>
  </nav>

  <!-- Main View Area -->
  <div class="flex-1 flex overflow-hidden">
    {#if currentTab === 'chat'}
      <!-- AI Chat Module -->
      <div class="flex-1 flex flex-col bg-slate-900 justify-between">
        <!-- Chat Top Bar -->
        <header class="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/60">
          <div class="flex items-center gap-3">
            <span class="font-bold text-sm text-indigo-300">Omni-Chat</span>
            <span class={`h-2 w-2 rounded-full ${connectionStatus === 'Backend Connected' ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
            <span class="text-xs text-slate-400">{connectionStatus}</span>
          </div>

          <div class="flex items-center gap-5">
            <!-- Knowledge Base Selector -->
            <div class="flex items-center gap-2">
              <label for="kb-select" class="text-xs text-slate-400">Knowledge Base:</label>
              <select
                id="kb-select"
                bind:value={selectedKbId}
                class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="">None (General Knowledge)</option>
                {#each knowledgeBases as kb}
                  <option value={kb.id}>{kb.name}</option>
                {/each}
              </select>
            </div>

            <!-- Voice Reply Toggle -->
            <div class="flex items-center gap-2 border-l border-slate-800 pl-4">
              <label for="voice-toggle" class="text-xs text-slate-400 cursor-pointer select-none">
                Voice Reply (Kokoro)
              </label>
              <input
                id="voice-toggle"
                type="checkbox"
                bind:checked={voiceReplyEnabled}
                class="h-4 w-4 accent-indigo-600 rounded cursor-pointer"
              />
            </div>
          </div>
        </header>

        <!-- Message History -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          {#if messages.length === 0}
            <div class="h-full flex flex-col items-center justify-center text-slate-500">
              <p class="text-lg font-medium">Multimodal AI Workspace Ready</p>
              <p class="text-xs mt-1">Speak into the mic, drop images for vision analysis, or type your query.</p>
            </div>
          {:else}
            {#each messages as msg}
              <div class={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div class={`max-w-2xl px-4 py-3 rounded-xl text-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'}`}>
                  {#if msg.image_paths && msg.image_paths.length > 0}
                    <div class="mb-2 text-xs text-indigo-200 flex items-center gap-1 font-mono">
                      🖼️ Attached: {msg.image_paths.length} image(s)
                    </div>
                  {/if}
                  <p class="whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            {/each}
          {/if}
        </div>

        <!-- Hidden Audio Player for Spoken Voice Replies -->
        <audio bind:this={audioElement} class="hidden"></audio>

        <!-- Unified Multimodal Input Bar -->
        <div class="p-4 border-t border-slate-800 bg-slate-950">
          <!-- Attachment Pills -->
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
            <!-- Attachment Button (Images & PDFs) -->
            <label
              class="p-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg cursor-pointer transition flex items-center justify-center"
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

            <!-- Push-to-Talk Mic Button -->
            <button
              type="button"
              on:click={toggleRecording}
              class={`p-2.5 rounded-lg border transition flex items-center justify-center ${
                isRecording
                  ? 'bg-rose-600 border-rose-500 text-white animate-pulse'
                  : 'bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300'
              }`}
              title={isRecording ? 'Click to Stop Recording' : 'Push-to-Talk (Microphone)'}
            >
              🎤
            </button>

            <!-- Prompt Input -->
            <input
              type="text"
              bind:value={promptText}
              on:keydown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder={isRecording ? 'Listening to voice...' : 'Ask question, analyze image, or speak...'}
              disabled={isStreaming}
              class="flex-1 bg-slate-800 text-slate-100 rounded-lg px-4 py-2.5 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
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
      <!-- Knowledge Base Module -->
      <div class="flex-1 p-8 overflow-y-auto space-y-6">
        <h2 class="text-xl font-bold">Knowledge Bases (LanceDB RAG)</h2>
        <div class="grid grid-cols-3 gap-4">
          {#each knowledgeBases as kb}
            <div class="bg-slate-900 border border-slate-800 rounded-lg p-5">
              <h3 class="font-bold text-indigo-400">{kb.name}</h3>
              <p class="text-xs text-slate-400 mt-1">{kb.description || 'No description'}</p>
              <div class="mt-4 text-xs text-slate-500">Model: {kb.embedding_model}</div>
            </div>
          {/each}
        </div>
      </div>

    {:else if currentTab === 'media'}
      <!-- Media Studio Module -->
      <div class="flex-1 p-8 overflow-y-auto space-y-8">
        <div>
          <h2 class="text-xl font-bold mb-4">Image Studio (ComfyUI)</h2>
          <div class="flex gap-3 max-w-2xl">
            <input
              type="text"
              bind:value={imagePrompt}
              placeholder="Describe image to generate..."
              class="flex-1 bg-slate-900 border border-slate-800 rounded px-4 py-2 text-sm"
            />
            <button
              on:click={triggerImageGen}
              class="bg-indigo-600 hover:bg-indigo-500 px-5 py-2 rounded text-sm font-medium"
            >
              Generate Image
            </button>
          </div>
        </div>

        <div>
          <h2 class="text-xl font-bold mb-4">Audio Studio (Kokoro TTS)</h2>
          <div class="flex gap-3 max-w-2xl">
            <input
              type="text"
              bind:value={ttsText}
              placeholder="Text to speak..."
              class="flex-1 bg-slate-900 border border-slate-800 rounded px-4 py-2 text-sm"
            />
            <button
              on:click={triggerTTS}
              class="bg-indigo-600 hover:bg-indigo-500 px-5 py-2 rounded text-sm font-medium"
            >
              Generate Speech
            </button>
          </div>
        </div>
      </div>

    {:else if currentTab === 'tasks'}
      <!-- Task Dashboard Module -->
      <div class="flex-1 p-8 overflow-y-auto">
        <h2 class="text-xl font-bold mb-6">Task Queue Operations</h2>
        <table class="w-full text-left text-sm border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 text-xs">
              <th class="py-2">Task Type</th>
              <th class="py-2">Status</th>
              <th class="py-2">Created At</th>
            </tr>
          </thead>
          <tbody>
            {#each tasks as t}
              <tr class="border-b border-slate-800/50">
                <td class="py-3 font-mono text-xs text-indigo-300">{t.task_type}</td>
                <td class="py-3">
                  <span class={`px-2 py-0.5 rounded text-xs ${t.status === 'completed' ? 'bg-emerald-950 text-emerald-400' : t.status === 'running' ? 'bg-amber-950 text-amber-400' : 'bg-slate-800 text-slate-300'}`}>
                    {t.status}
                  </span>
                </td>
                <td class="py-3 text-xs text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

    {:else if currentTab === 'settings'}
      <!-- Settings & Hardware Module -->
      <div class="flex-1 p-8 overflow-y-auto max-w-2xl space-y-6">
        <h2 class="text-xl font-bold">System & Settings</h2>

        <div class="bg-slate-900 p-5 rounded-lg border border-slate-800 space-y-3">
          <h3 class="text-sm font-semibold text-slate-300">Authentication Token</h3>
          <input
            type="password"
            bind:value={token}
            on:input={refreshAllData}
            placeholder="Paste session token..."
            class="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
          />
        </div>

        {#if supervisorStatus}
          <div class="bg-slate-900 p-5 rounded-lg border border-slate-800 space-y-3">
            <h3 class="text-sm font-semibold text-slate-300">Model Supervisor & VRAM</h3>
            <div class="text-xs space-y-1 font-mono text-slate-400">
              <p>Model State: <span class="text-indigo-400">{supervisorStatus.state}</span></p>
              <p>Active Model: {supervisorStatus.active_model_name || 'None'}</p>
              <p>VRAM Free: {supervisorStatus.vram?.free_mb} MB / {supervisorStatus.vram?.total_mb} MB</p>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>
