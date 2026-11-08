<script lang="ts">
  import { onMount } from 'svelte';
  import ChatHeader from './components/chat/ChatHeader.svelte';
  import ChatSidebar from './components/chat/ChatSidebar.svelte';
  import InputBar from './components/chat/InputBar.svelte';
  import MessageList from './components/chat/MessageList.svelte';
  import ImageStudio from './components/studios/ImageStudio.svelte';
  import VoiceStudio from './components/studios/VoiceStudio.svelte';
  import HuggingFaceView from './components/views/HuggingFaceView.svelte';
  import KnowledgeView from './components/views/KnowledgeView.svelte';
  import SettingsView from './components/views/SettingsView.svelte';
  import TasksView from './components/views/TasksView.svelte';

  import { apiFetch, ensureToken } from './lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    activeModelId,
    characters,
    conversations,
    currentTab,
    registeredModels,
    sessionToken,
    supervisorStatus,
  } from './lib/stores';

  let activeMode: 'text' | 'image' | 'voice' = 'text';
  let messages: { role: string; content: string; image_paths?: string[] }[] = [];
  let isStreaming = false;

  async function init() {
    await ensureToken();
    const [convRes, modelRes, charRes, statusRes] = await Promise.all([
      apiFetch('/conversations'),
      apiFetch('/models'),
      apiFetch('/characters'),
      apiFetch('/models/status'),
    ]);

    if (convRes.ok) {
      $conversations = await convRes.json();
      if ($conversations.length > 0 && !$activeConversationId) {
        loadConversation($conversations[0].id);
      }
    }
    if (modelRes.ok) $registeredModels = await modelRes.json();
    if (charRes.ok) {
      $characters = await charRes.json();
      if ($characters.length > 0 && !$activeCharacterId) $activeCharacterId = $characters[0].id;
    }
    if (statusRes.ok) {
      $supervisorStatus = await statusRes.json();
      $activeModelId = $supervisorStatus.active_model_id || '';
    }
  }

  async function loadConversation(id: string) {
    $activeConversationId = id;
    const res = await apiFetch(`/conversations/${id}`);
    if (res.ok) {
      const data = await res.json();
      messages = data.messages.map((m: any) => ({ role: m.role, content: m.content }));
    }
  }

  async function handleSend(text: string, images: string[]) {
    if (!$activeConversationId) {
      const convRes = await apiFetch('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: text.slice(0, 30) }),
      });
      if (convRes.ok) {
        const c = await convRes.json();
        $conversations = [c, ...$conversations];
        $activeConversationId = c.id;
      }
    }

    messages = [...messages, { role: 'user', content: text, image_paths: images }];
    isStreaming = true;
    const assistantIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];

    try {
      const response = await apiFetch('/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: $activeConversationId,
          character_id: $activeCharacterId,
          messages: messages.slice(0, -1),
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());
              if (data.text) {
                messages[assistantIdx].content += data.text;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }
    } finally {
      isStreaming = false;
    }
  }

  onMount(init);
</script>

<div class="flex h-screen bg-slate-950 text-slate-100 font-sans flex-col">
  <!-- Top-Level Prominent Modality Bar (Choice 2 A) -->
  <header class="h-14 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between select-none shadow-md">
    <div class="flex items-center gap-3">
      <div class="h-8 w-8 bg-indigo-600 rounded-lg flex items-center justify-center font-black text-sm text-white">
        A
      </div>
      <span class="font-bold text-sm tracking-tight text-slate-200">AIWA Workstation</span>
    </div>

    <!-- 3 Prominent Content Studios -->
    <div class="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
      <button
        on:click={() => { activeMode = 'text'; $currentTab = 'chat'; }}
        class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
          activeMode === 'text' && $currentTab === 'chat'
            ? 'bg-indigo-600 text-white shadow'
            : 'text-slate-400 hover:text-slate-200'
        }`}
      >
        💬 Text & Vision
      </button>

      <button
        on:click={() => { activeMode = 'image'; $currentTab = 'media'; }}
        class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
          activeMode === 'image' && $currentTab === 'media'
            ? 'bg-indigo-600 text-white shadow'
            : 'text-slate-400 hover:text-slate-200'
        }`}
      >
        🎨 Image Studio
      </button>

      <button
        on:click={() => { activeMode = 'voice'; $currentTab = 'tasks'; }}
        class={`px-4 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
          activeMode === 'voice' && $currentTab === 'tasks'
            ? 'bg-indigo-600 text-white shadow'
            : 'text-slate-400 hover:text-slate-200'
        }`}
      >
        🎙️ Voice Studio
      </button>
    </div>

    <!-- Utility Tabs -->
    <div class="flex items-center gap-2">
      <button on:click={() => ($currentTab = 'knowledge')} class={`px-2.5 py-1 rounded text-xs transition ${$currentTab === 'knowledge' ? 'bg-slate-800 text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`} title="RAG Knowledge">📚</button>
      <button on:click={() => ($currentTab = 'hf')} class={`px-2.5 py-1 rounded text-xs transition ${$currentTab === 'hf' ? 'bg-slate-800 text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`} title="HuggingFace Hub">🌐</button>
      <button on:click={() => ($currentTab = 'settings')} class={`px-2.5 py-1 rounded text-xs transition ${$currentTab === 'settings' ? 'bg-slate-800 text-indigo-400' : 'text-slate-400 hover:text-slate-200'}`} title="Settings">⚙️</button>
    </div>
  </header>

  <!-- Workspace Studio Body -->
  <div class="flex-1 flex overflow-hidden">
    {#if $currentTab === 'chat'}
      <ChatSidebar onSelectConversation={loadConversation} />
      <div class="flex-1 flex flex-col bg-slate-900">
        <ChatHeader />
        <MessageList {messages} onSelectQuickPrompt={(prompt) => handleSend(prompt, [])} />
        <InputBar {isStreaming} onSendMessage={handleSend} />
      </div>
    {:else if $currentTab === 'media'}
      <ImageStudio />
    {:else if $currentTab === 'tasks'}
      <VoiceStudio />
    {:else if $currentTab === 'knowledge'}
      <KnowledgeView />
    {:else if $currentTab === 'hf'}
      <HuggingFaceView />
    {:else if $currentTab === 'settings'}
      <SettingsView />
    {/if}
  </div>
</div>
