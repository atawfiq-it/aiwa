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

  async function waitForBackendAndHydrate() {
    // Poll /health up to 30 times (15 seconds) while backend sidecar boots up
    let backendReady = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      try {
        const health = await fetch('http://127.0.0.1:8000/api/v1/health');
        if (health.ok) {
          backendReady = true;
          break;
        }
      } catch {}
      await new Promise((r) => setTimeout(r, 500));
    }

    if (!backendReady) {
      console.error('[AIWA] Timed out waiting for backend daemon.');
      return;
    }

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
      const charData = await charRes.json();
      $characters = charData;
      if (charData.length > 0 && !$activeCharacterId) {
        activeCharacterId.set(charData[0].id);
      }
    }
    if (statusRes.ok) {
      const status = await statusRes.json();
      $supervisorStatus = status;
      $activeModelId = status.active_model_id || '';
    }
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
      const charData = await charRes.json();
      $characters = charData;
      if (charData.length > 0 && !$activeCharacterId) {
        activeCharacterId.set(charData[0].id);
      }
    }
    if (statusRes.ok) {
      const status = await statusRes.json();
      $supervisorStatus = status;
      $activeModelId = status.active_model_id || '';
    }
  
  onMount(() => {
    waitForBackendAndHydrate();
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
