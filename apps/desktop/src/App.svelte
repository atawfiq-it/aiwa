<script lang="ts">
  import { onMount } from 'svelte';
  import Navigation from './components/Navigation.svelte';
  import ChatHeader from './components/chat/ChatHeader.svelte';
  import ChatSidebar from './components/chat/ChatSidebar.svelte';
  import InputBar from './components/chat/InputBar.svelte';
  import HuggingFaceView from './components/views/HuggingFaceView.svelte';
  import SettingsView from './components/views/SettingsView.svelte';
  import { apiFetch } from './lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    activeModelId,
    characters,
    conversations,
    currentTab,
    imageGenMode,
    registeredModels,
    sessionToken,
  } from './lib/stores';

  let messages: { role: string; content: string; image_paths?: string[] }[] = [];
  let isStreaming = false;

  async function init() {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const token = await invoke<string>('get_session_token');
      if (token) $sessionToken = token;
    } catch {}

    const convRes = await apiFetch('/conversations');
    if (convRes.ok) $conversations = await convRes.json();

    const modelRes = await apiFetch('/models');
    if (modelRes.ok) $registeredModels = await modelRes.json();

    const charRes = await apiFetch('/characters');
    if (charRes.ok) {
      $characters = await charRes.json();
      if ($characters.length > 0 && !$activeCharacterId) $activeCharacterId = $characters[0].id;
    }

    const statusRes = await apiFetch('/models/status');
    if (statusRes.ok) {
      const status = await statusRes.json();
      $activeModelId = status.active_model_id || '';
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
          image_gen_mode: $imageGenMode,
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

<div class="flex h-screen bg-slate-950 text-slate-100 font-sans">
  <Navigation />

  <div class="flex-1 flex overflow-hidden">
    {#if $currentTab === 'chat'}
      <ChatSidebar onSelectConversation={loadConversation} />
      <div class="flex-1 flex flex-col bg-slate-900">
        <ChatHeader />
        <!-- Message Bubbles -->
        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          {#each messages as msg}
            <div class={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div class={`max-w-2xl px-4 py-3 rounded-xl text-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'}`}>
                <p class="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          {/each}
        </div>
        <InputBar {isStreaming} onSendMessage={handleSend} />
      </div>
    {:else if $currentTab === 'hf'}
      <HuggingFaceView />
    {:else if $currentTab === 'settings'}
      <SettingsView />
    {/if}
  </div>
</div>
