<script lang="ts">
  import { onMount } from 'svelte';
  import ChatWorkspace from './components/chat/ChatWorkspace.svelte';
  import AgentStudio from './components/studios/AgentStudio.svelte';
  import ImageStudio from './components/studios/ImageStudio.svelte';
  import VoiceStudio from './components/studios/VoiceStudio.svelte';
  import HuggingFaceView from './components/views/HuggingFaceView.svelte';
  import KnowledgeView from './components/views/KnowledgeView.svelte';
  import SettingsView from './components/views/SettingsView.svelte';
  import TasksView from './components/views/TasksView.svelte';
  import { apiFetch, ensureToken } from './lib/api';
  import {
    activeCharacterId,
    activeModelId,
    characters,
    connectionStatus,
    conversations,
    currentTab,
    currentTheme,
    registeredModels,
    supervisorStatus,
  } from './lib/stores';
  import TopHeader from './components/layouts/TopHeader.svelte';

  $: if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', $currentTheme);
  }

  async function waitForBackendAndHydrate() {
    // 1. Poll /health up to 30 times (15s) while backend sidecar boots
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
      connectionStatus.set('Backend Offline');
      console.error('[AIWA UI] Timed out waiting for backend daemon on port 8000.');
      return;
    }

    connectionStatus.set('Backend Connected');
    await ensureToken();

    // 2. Fetch initial workspace datasets concurrently
    const [convRes, modelRes, charRes, statusRes] = await Promise.all([
      apiFetch('/conversations'),
      apiFetch('/models'),
      apiFetch('/characters'),
      apiFetch('/models/status'),
    ]);

    if (convRes.ok) {
      const convData = await convRes.json();
      conversations.set(convData);
      console.log(`[AIWA UI] Loaded ${convData.length} conversation(s).`);
    }

    if (modelRes.ok) {
      const modelsData = await modelRes.json();
      registeredModels.set(modelsData);
      console.log('[AIWA UI] GET /models ->', modelsData);
    } else {
      console.error('[AIWA UI] GET /models FAILED -> HTTP', modelRes.status);
    }

    if (charRes.ok) {
      const charData = await charRes.json();
      characters.set(charData);
      console.log('[AIWA UI] GET /characters ->', charData);
      if (charData.length > 0) {
        const savedCharId = localStorage.getItem('aiwa_active_character_id');
        const validSaved = charData.find((c: any) => c.id === savedCharId);
        const target = validSaved || charData[0];
        activeCharacterId.set(target.id);
        localStorage.setItem('aiwa_active_character_id', target.id);
        localStorage.setItem('aiwa_active_character_name', target.name);
      }
    } else {
      console.error('[AIWA UI] GET /characters FAILED -> HTTP', charRes.status);
    }

    if (statusRes.ok) {
      const status = await statusRes.json();
      supervisorStatus.set(status);
      activeModelId.set(status.active_model_id || '');
    }
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
