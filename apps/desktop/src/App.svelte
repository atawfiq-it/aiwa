<script lang="ts">
  import { onMount } from 'svelte';
  import ChatWorkspace from './components/chat/ChatWorkspace.svelte';
  import TopHeader from './components/layouts/TopHeader.svelte';
  import ImageStudio from './components/studios/ImageStudio.svelte';
  import VoiceStudio from './components/studios/VoiceStudio.svelte';
  import AgentStudio from './components/studios/AgentStudio.svelte';
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
    currentTheme,
    registeredModels,
    supervisorStatus,
  } from './lib/stores';

  $: if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', $currentTheme);
  }

  onMount(async () => {
    await ensureToken();
    const [convRes, modelRes, charRes, statusRes] = await Promise.all([
      apiFetch('/conversations'),
      apiFetch('/models'),
      apiFetch('/characters'),
      apiFetch('/models/status'),
    ]);

    if (convRes.ok) $conversations = await convRes.json();
    if (modelRes.ok) $registeredModels = await modelRes.json();
    if (charRes.ok) {
      $characters = await charRes.json();
      if ($characters.length > 0 && !$activeCharacterId) $activeCharacterId = $characters[0].id;
    }
    if (statusRes.ok) {
      const status = await statusRes.json();
      $supervisorStatus = status;
      $activeModelId = status.active_model_id || '';
    }
  });
</script>

<div class="flex h-screen bg-[var(--bg-base)] text-[var(--text-main)] font-sans flex-col overflow-hidden">
  <TopHeader />

  <main class="flex-1 flex overflow-hidden">
    {#if $currentTab === 'chat'}
      <ChatWorkspace />
    {:else if $currentTab === 'media'}
      <ImageStudio />
    {:else if $currentTab === 'voice'}
      <VoiceStudio />
    {:else if $currentTab === 'agent'}
      <AgentStudio />
    {:else if $currentTab === 'tasks'}
      <TasksView />
    {:else if $currentTab === 'knowledge'}
      <KnowledgeView />
    {:else if $currentTab === 'hf'}
      <HuggingFaceView />
    {:else if $currentTab === 'settings'}
      <SettingsView />
    {/if}
  </main>
</div>
