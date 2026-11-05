<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    activeModelId,
    characters,
    imageGenMode,
    registeredModels,
    sessionToken,
  } from '../../lib/stores';

  let selectedDropdownModelId = $activeModelId;
  let isSwitching = false;

  $: if ($activeModelId && !selectedDropdownModelId) selectedDropdownModelId = $activeModelId;

  async function applyModelSwitch() {
    if (!selectedDropdownModelId || selectedDropdownModelId === $activeModelId) return;
    isSwitching = true;
    try {
      const res = await apiFetch(`/models/${selectedDropdownModelId}/load`, { method: 'POST' });
      if (res.ok) {
        $activeModelId = selectedDropdownModelId;
        alert('Model loaded successfully!');
      }
    } finally {
      isSwitching = false;
    }
  }

  function exportMarkdown() {
    if (!$activeConversationId) return;
    window.open(`http://127.0.0.1:8000/api/v1/conversations/${$activeConversationId}/export?token=${$sessionToken}`, '_blank');
  }
</script>

<header class="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/80">
  <div class="flex items-center gap-3">
    <!-- Model Selector -->
    <select bind:value={selectedDropdownModelId} class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none">
      {#each $registeredModels as m}
        <option value={m.id}>{m.display_name} {m.vision_supported ? '👁️' : ''} {m.id === $activeModelId ? '(Active)' : ''}</option>
      {/each}
    </select>

    {#if selectedDropdownModelId && selectedDropdownModelId !== $activeModelId}
      <button on:click={applyModelSwitch} disabled={isSwitching} class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded animate-pulse">
        {isSwitching ? 'Loading...' : 'Apply Switch'}
      </button>
    {/if}

    <!-- Persona Selector -->
    <select bind:value={$activeCharacterId} class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none">
      {#each $characters as c}
        <option value={c.id}>{c.avatar_emoji} {c.name}</option>
      {/each}
    </select>

    <!-- Image Gen Mode -->
    <select bind:value={$imageGenMode} class="bg-slate-800 text-xs text-slate-200 border border-slate-700 rounded px-2.5 py-1.5 focus:outline-none">
      <option value="none">🎨 Img: None</option>
      <option value="probable">🎨 Img: Probable (50%)</option>
      <option value="definitely">🎨 Img: Definitely</option>
    </select>
  </div>

  <button on:click={exportMarkdown} disabled={!$activeConversationId} class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 rounded-lg transition disabled:opacity-40">
    📥 Export Record (.md)
  </button>
</header>
