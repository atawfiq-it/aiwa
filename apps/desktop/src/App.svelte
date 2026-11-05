<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = 'http://127.0.0.1:8888/api/v1';

  // Navigation
  let currentTab: 'chat' | 'knowledge' | 'media' | 'tasks' | 'settings' = 'chat';
  let token = '';
  let connectionStatus = 'Connecting...';

  // Conversations & Chat
  let conversations: any[] = [];
  let currentConversationId: string | null = null;
  let messages: { id?: string; role: string; content: string; image_paths?: string[] }[] = [];
  let promptText = '';
  let isStreaming = false;

  // Multimodal Input Bar State
  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let voiceReplyEnabled = false;
  let attachedFiles: { name: string; path: string; type: string }[] = [];
  let activeAudioUrl: string | null = null;
  let audioElement: HTMLAudioElement;

  // Models & VRAM Supervisor
  let registeredModels: any[] = [];
  let activeModelId: string = '';
  let selectedDropdownModelId: string = '';
  let isSwitchingModel = false;
  let supervisorStatus: any = null;

  // Deep Scanner State
  let customScanPaths: string = '';
  let scannedModelsList: any[] = [];
  let isScanning = false;

  // Knowledge Base & Media State
  let knowledgeBases: any[] = [];
  let selectedKbId: string = '';
  let imagePrompt = '';
  let mediaGallery: any[] = [];
  let ttsText = '';
  let tasks: any[] = [];

  // ==========================================
  // Lifecycle & Initialization
  // ==========================================
  async function loadInitialData() {
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
      const res = await fetch('http://127.0.0.1:8888/api/v1/health');
      connectionStatus = res.ok ? 'Backend Connected' : 'Backend Offline';
    } catch {
      connectionStatus = 'Backend Offline';
    }
  }

  async function refreshAllData() {
    await loadConversations();
    await loadRegisteredModels();
    await loadSupervisorStatus();
    await loadSavedDirectories();
    await loadKnowledgeBases();
    await loadTasks();
    await loadGallery();
  }

  // ==========================================
  // Conversations Management
  // ==========================================
  async function loadConversations() {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        conversations = await res.json();
        if (conversations.length > 0 && !currentConversationId) {
          await selectConversation(conversations[0].id);
        }
      }
    } catch {}
  }

  async function createNewConversation() {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ title: 'New Conversation' }),
      });
      if (res.ok) {
        const newConv = await res.json();
        conversations = [newConv, ...conversations];
        await selectConversation(newConv.id);
      }
    } catch {}
  }

  async function selectConversation(id: string) {
    currentConversationId = id;
    try {
      const res = await fetch(`${API_BASE}/conversations/${id}`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        const data = await res.json();
        messages = data.messages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        }));
      }
    } catch {}
  }

  async function deleteConversation(id: string, event: Event) {
    event.stopPropagation();
    if (!confirm('Are you sure you want to delete this conversation?')) return;

    try {
      const res = await fetch(`${API_BASE}/conversations/${id}`, {
        method: 'DELETE',
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        conversations = conversations.filter((c) => c.id !== id);
        if (currentConversationId === id) {
          if (conversations.length > 0) {
            await selectConversation(conversations[0].id);
          } else {
            currentConversationId = null;
            messages = [];
          }
        }
      }
    } catch {}
  }

  function downloadChatMarkdown() {
    if (!currentConversationId) return;
    window.open(`${API_BASE}/conversations/${currentConversationId}/export`, '_blank');
  }

  // ==========================================
  // Push-to-Talk Microphone (Web Audio)
  // ==========================================
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
      alert('Microphone error: ' + err.message);
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

  // ==========================================
  // File Uploads (Images & Documents)
  // ==========================================
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
      } catch (err) {
        console.error('File upload failed:', err);
      }
    }
  }

  function removeAttachment(index: number) {
    attachedFiles = attachedFiles.filter((_, i) => i !== index);
  }

  // ==========================================
  // Chat Messaging & SSE Streaming
  // ==========================================
  async function sendMessage() {
    if ((!promptText.trim() && attachedFiles.length === 0) || isStreaming) return;

    if (!currentConversationId) {
      await createNewConversation();
    }

    const currentImages = attachedFiles
      .filter((f) => f.type.startsWith('image/'))
      .map((f) => f.path);

    const userText = promptText;
    const userMessage = { role: 'user', content: userText, image_paths: currentImages };
    messages = [...messages, userMessage];
    promptText = '';
    attachedFiles = [];
    isStreaming = true;

    // Persist to database (triggers auto-title generation if new)
    fetch(`${API_BASE}/conversations/${currentConversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
      body: JSON.stringify(userMessage),
    }).then(() => loadConversations());

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

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        messages[assistantIndex].content = `⚠️ Error: ${err.detail || 'Inference failed'}`;
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
    } catch (e: any) {
      messages[assistantIndex].content = `⚠️ Network Error: ${e.message}`;
      messages = [...messages];
    } finally {
      isStreaming = false;
    }
  }

  async function playVoiceReply(text: string) {
    try {
      const res = await fetch(`${API_BASE}/media/audio/speech-direct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
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
      console.error('Voice playback failed:', e);
    }
  }

  // ==========================================
  // Model Switcher & Supervisor
  // ==========================================
  async function loadRegisteredModels() {
    try {
      const res = await fetch(`${API_BASE}/models`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) registeredModels = await res.json();
    } catch {}
  }

  async function loadSupervisorStatus() {
    try {
      const res = await fetch(`${API_BASE}/models/status`, {
        headers: { 'X-AIWA-Token': token },
      });
      if (res.ok) {
        supervisorStatus = await res.json();
        activeModelId = supervisorStatus.active_model_id || '';
        if (!selectedDropdownModelId) selectedDropdownModelId = activeModelId;
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
        alert('Model successfully loaded!');
      } else {
        const err = await res.json();
        alert(`Failed: ${err.detail || 'Could not load model'}`);
      }
    } catch (e: any) {
      alert(`Network error: ${e.message}`);
    } finally {
      isSwitchingModel = false;
    }
  }

  // ==========================================
  // Deep Recursive Scanner
  // ==========================================
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

  async function triggerDeepScan() {
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

  // ==========================================
  // Media Studio, RAG & Tasks
  // ==========================================
  async function loadKnowledgeBases() {
    try {
      const res = await fetch(`${API_BASE}/knowledge-bases`, { headers: { 'X-AIWA-Token': token } });
      if (res.ok) knowledgeBases = await res.json();
    } catch {}
  }

  async function loadTasks() {
    try {
      const res = await fetch(`${API_BASE}/tasks`, { headers: { 'X-AIWA-Token': token } });
      if (res.ok) tasks = await res.json();
    } catch {}
  }

  async function loadGallery() {
    try {
      const res = await fetch(`${API_BASE}/media/gallery`, { headers: { 'X-AIWA-Token': token } });
      if (res.ok) mediaGallery = await res.json();
    } catch {}
  }

  async function triggerImageGen() {
    if (!imagePrompt.trim()) return;
    try {
      await fetch(`${API_BASE}/media/images/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-AIWA-Token': token },
        body: JSON.stringify({ prompt: imagePrompt }),
      });
      imagePrompt = '';
      await loadTasks();
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
      await loadTasks();
    } catch {}
  }

  onMount(() => {
    loadInitialData();
    const interval = setInterval(() => {
      checkBackend();
      if (token) {
        if (currentTab === 'tasks') loadTasks();
        if (currentTab === 'media') loadGallery();
      }
    }, 3000);
    return () => clearInterval(interval);
  });
</script>

<div class="flex h-screen bg-slate-950 text-slate-100 font-sans select-none">
  <!-- Left Navigation Bar -->
  <nav class="w-16 bg-slate-900 border-r border-slate-800 flex flex-col items-center py-4 space-y-6 z-20">
    <div class="h-10 w-10 bg-indigo-600 rounded-xl flex items-center justify-center font-bold text-lg text-white shadow-lg">
      A
    </div>

    <div class="flex flex-col space-y-3 w-full px-2">
      <button
        on:click={() => (currentTab = 'chat')}
        class={`p-3 rounded-xl flex justify-center transition ${currentTab === 'chat' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-800'}`}
        title="AI Chat & Vision"
      >
        💬
      </button>

      <button
        on:click={() => { currentTab = 'knowledge'; loadKnowledgeBases(); }}
        class={`p-3 rounded-xl flex justify-center transition ${currentTab === 'knowledge' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Knowledge Base (RAG)"
      >
        📚
      </button>

      <button
        on:click={() => { currentTab = 'media'; loadGallery(); }}
        class={`p-3 rounded-xl flex justify-center transition ${currentTab === 'media' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Media Studio"
      >
        🎨
      </button>

      <button
        on:click={() => { currentTab = 'tasks'; loadTasks(); }}
        class={`p-3 rounded-xl flex justify-center transition ${currentTab === 'tasks' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Task Dashboard"
      >
        ⚡
      </button>

      <button
        on:click={() => { currentTab = 'settings'; loadSavedDirectories(); loadSupervisorStatus(); }}
        class={`p-3 rounded-xl flex justify-center transition ${currentTab === 'settings' ? 'bg-indigo-600 text-white shadow-md' : 'text-slate-400 hover:bg-slate-800'}`}
        title="Multi-Drive Scanner & Settings"
      >
        ⚙️
      </button>
    </div>
  </nav>

  <!-- Workspace Container -->
  <div class="flex-1 flex overflow-hidden">
    {#if currentTab === 'chat'}
      <!-- Persistent Chat History Sidebar -->
      <aside class="w-64 bg-slate-900/60 border-r border-slate-800 flex flex-col justify-between">
        <div class="p-4 flex flex-col h-full overflow-hidden">
          <button
            on:click={createNewConversation}
            class="w-full py-2.5 px-3 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow"
          >
            <span>+</span> New Conversation
          </button>

          <!-- Conversation List -->
          <div class="flex-1 overflow-y-auto mt-4 space-y-1 pr-1">
            {#each conversations as c}
              <div
                on:click={() => selectConversation(c.id)}
                class={`group flex items-center justify-between p-2.5 rounded-lg text-xs cursor-pointer transition ${c.id === currentConversationId ? 'bg-slate-800 text-indigo-300 font-semibold border border-slate-700' : 'text-slate-400 hover:bg-slate-800/50'}`}
              >
                <span class="truncate flex-1 mr-2">{c.title}</span>
                <button
                  on:click={(e) => deleteConversation(c.id, e)}
                  class="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 transition"
                  title="Delete Conversation"
                >
                  ✕
                </button>
              </div>
            {/each}
          </div>
        </div>
      </aside>

      <!-- Main Chat Area -->
      <div class="flex-1 flex flex-col bg-slate-900">
        <!-- Chat Header -->
        <header class="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/80">
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-400">Model:</span>
            <select
              bind:value={selectedDropdownModelId}
              class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              {#each registeredModels as m}
                <option value={m.id}>
                  {m.display_name} {m.vision_supported ? '👁️' : ''} {m.id === activeModelId ? '(Active)' : ''}
                </option>
              {/each}
            </select>

            <!-- Explicit Apply Switch Button -->
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

          <div class="flex items-center gap-4">
            <!-- RAG Knowledge Base Dropdown -->
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400">Context:</span>
              <select
                bind:value={selectedKbId}
                class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="">None (Standard)</option>
                {#each knowledgeBases as kb}
                  <option value={kb.id}>{kb.name}</option>
                {/each}
              </select>
            </div>

            <!-- Voice Reply Toggle -->
            <label class="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
              <input type="checkbox" bind:checked={voiceReplyEnabled} class="accent-indigo-600 rounded" />
              <span>Voice Reply</span>
            </label>

            <!-- Rich Markdown Export -->
            <button
              on:click={downloadChatMarkdown}
              disabled={!currentConversationId || messages.length === 0}
              class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-40 text-xs text-slate-300 rounded-lg flex items-center gap-1.5 transition"
            >
              📥 Export (.md)
            </button>
          </div>
        </header>

        <!-- Message List -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          {#if messages.length === 0}
            <div class="h-full flex flex-col items-center justify-center text-slate-500">
              <p class="text-base font-medium">Ready for local multimodal inference</p>
              <p class="text-xs mt-1">Speak into the mic, attach images/PDFs, or type your prompt.</p>
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

        <!-- Hidden Audio Element for Voice Replies -->
        <audio bind:this={audioElement} class="hidden"></audio>

        <!-- Multimodal Input Bar -->
        <div class="p-4 border-t border-slate-800 bg-slate-900/80">
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
            <!-- File Attachment Picker -->
            <label class="p-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg cursor-pointer transition" title="Attach Image or PDF">
              📎
              <input type="file" accept="image/*,application/pdf" multiple on:change={handleFileUpload} class="hidden" />
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
              title={isRecording ? 'Click to Stop Recording' : 'Push-to-Talk (Microphone)'}
            >
              🎤
            </button>

            <!-- Prompt Input -->
            <input
              type="text"
              bind:value={promptText}
              on:keydown={(e) => e.key === 'Enter' && sendMessage()}
              placeholder={isRecording ? 'Listening to speech...' : 'Type a question or analyze attachments...'}
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
      <!-- Knowledge Bases Explorer -->
      <div class="flex-1 p-8 overflow-y-auto space-y-6">
        <h2 class="text-xl font-bold">Knowledge Bases (LanceDB Local RAG)</h2>
        <div class="grid grid-cols-3 gap-4">
          {#each knowledgeBases as kb}
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h3 class="font-bold text-indigo-400">{kb.name}</h3>
              <p class="text-xs text-slate-400 mt-1">{kb.description || 'No description provided'}</p>
              <div class="mt-4 text-[11px] text-slate-500 font-mono">Model: {kb.embedding_model}</div>
            </div>
          {/each}
        </div>
      </div>

    {:else if currentTab === 'media'}
      <!-- Media Studio (ComfyUI & Kokoro) -->
      <div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl">
        <div>
          <h2 class="text-xl font-bold mb-4">🎨 Image Studio (ComfyUI Embedded)</h2>
          <div class="flex gap-3">
            <input
              type="text"
              bind:value={imagePrompt}
              placeholder="Describe artwork to render..."
              class="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
            <button on:click={triggerImageGen} class="bg-indigo-600 hover:bg-indigo-500 px-5 py-2 rounded-lg text-sm font-semibold">
              Generate
            </button>
          </div>
        </div>

        <div>
          <h2 class="text-xl font-bold mb-4">🔊 Audio Studio (Kokoro-82M TTS)</h2>
          <div class="flex gap-3">
            <input
              type="text"
              bind:value={ttsText}
              placeholder="Text to speak..."
              class="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
            <button on:click={triggerTTS} class="bg-indigo-600 hover:bg-indigo-500 px-5 py-2 rounded-lg text-sm font-semibold">
              Speak
            </button>
          </div>
        </div>
      </div>

    {:else if currentTab === 'tasks'}
      <!-- Background Task Operations -->
      <div class="flex-1 p-8 overflow-y-auto">
        <h2 class="text-xl font-bold mb-6">Background Task Operations</h2>
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
              <tr class="border-b border-slate-800/50">
                <td class="py-3 font-mono text-xs text-indigo-300">{t.task_type}</td>
                <td class="py-3">
                  <span class={`px-2.5 py-0.5 rounded text-xs ${t.status === 'completed' ? 'bg-emerald-950 text-emerald-400' : t.status === 'running' ? 'bg-amber-950 text-amber-400' : 'bg-slate-800 text-slate-300'}`}>
                    {t.status}
                  </span>
                </td>
                <td class="py-3 text-xs">{t.progress_percent}%</td>
                <td class="py-3 text-xs text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

    {:else if currentTab === 'settings'}
      <!-- Deep Recursive Multi-Modal Scanner & System Settings -->
      <div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl">
        <div>
          <h2 class="text-xl font-bold text-slate-100">Local Multi-Drive Model Catalog</h2>
          <p class="text-xs text-slate-400 mt-1">Deep recursive scanning across all directory levels for LLM (.gguf), Image Diffusion (.safetensors), and Voice (.onnx) models.</p>
        </div>

        <div class="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
          <label for="settings-custom-dirs" class="text-xs font-semibold text-slate-300 block">Search Root Directories (all sub-directories scanned recursively):</label>
          <textarea
            id="settings-custom-dirs"
            rows="3"
            bind:value={customScanPaths}
            class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
          ></textarea>

          <button
            on:click={triggerDeepScan}
            disabled={isScanning}
            class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded-lg transition"
          >
            {isScanning ? 'Scanning All Sub-directories...' : '🔍 Run Deep Recursive Scan'}
          </button>
        </div>

        <!-- Scanned Models Catalog -->
        {#if scannedModelsList.length > 0}
          <div class="space-y-3">
            <h3 class="text-sm font-semibold text-slate-300">Cataloged Models ({scannedModelsList.length}):</h3>
            <div class="grid grid-cols-1 gap-2.5">
              {#each scannedModelsList as model}
                <div class="bg-slate-900 border border-slate-800 p-3.5 rounded-xl flex items-center justify-between">
                  <div>
                    <div class="flex items-center gap-2">
                      <span class={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${model.category === 'llm' ? 'bg-indigo-950 text-indigo-300 border border-indigo-700' : model.category === 'diffusion' ? 'bg-purple-950 text-purple-300 border border-purple-700' : 'bg-emerald-950 text-emerald-300 border border-emerald-700'}`}>
                        {model.category}
                      </span>
                      <span class="font-bold text-sm text-slate-200">{model.display_name}</span>
                      {#if model.vision_supported}
                        <span class="text-xs text-indigo-400">👁️ Vision</span>
                      {/if}
                    </div>
                    <p class="text-[11px] text-slate-400 font-mono mt-1 truncate max-w-xl">{model.file_path}</p>
                    <p class="text-[10px] text-slate-500">Size: {model.file_size_gb} GB • {model.quantization || 'standard'}</p>
                  </div>

                  {#if model.category === 'llm'}
                    <button
                      on:click={() => registerScannedModel(model)}
                      class="px-3.5 py-1.5 bg-slate-800 hover:bg-indigo-600 border border-slate-700 hover:border-indigo-500 text-xs font-medium rounded-lg transition"
                    >
                      + Register Model
                    </button>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- System & VRAM Dashboard -->
        {#if supervisorStatus}
          <div class="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-2">
            <h3 class="text-sm font-semibold text-slate-300">Model Supervisor & VRAM Budget (80% Ceiling)</h3>
            <div class="text-xs font-mono text-slate-400 space-y-1">
              <p>Active Model: <span class="text-indigo-400">{supervisorStatus.active_model_name || 'None'}</span></p>
              <p>State: <span class="text-emerald-400">{supervisorStatus.state}</span></p>
              <p>VRAM Free: {supervisorStatus.vram?.free_mb} MB / {supervisorStatus.vram?.total_mb} MB (Allowed Cap: {supervisorStatus.vram?.allowed_ceiling_mb} MB)</p>
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>
