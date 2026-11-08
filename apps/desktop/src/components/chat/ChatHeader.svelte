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
    supervisorStatus,
  } from '../../lib/stores';

  let selectedDropdownModelId = '';
  let isSwitching = false;

  $: if ($activeModelId && !selectedDropdownModelId) {
    selectedDropdownModelId = $activeModelId;
  }

  async function applyModelSwitch() {
    if (!selectedDropdownModelId || selectedDropdownModelId === $activeModelId) return;
    isSwitching = true;
    try {
      const res = await apiFetch(`/models/${selectedDropdownModelId}/load`, { method: 'POST' });
      if (res.ok) {
        $activeModelId = selectedDropdownModelId;
        const statusRes = await apiFetch('/models/status');
        if (statusRes.ok) $supervisorStatus = await statusRes.json();
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

<header class="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/90 backdrop-blur select-none">
  <div class="flex items-center gap-3">
    <!-- Model Selector with Icon Badge -->
    <div class="flex items-center gap-2 bg-slate-800/80 border border-slate-700/80 rounded-lg px-2.5 py-1">
      <span class="text-xs text-slate-400 font-medium">Model:</span>
      <select
        bind:value={selectedDropdownModelId}
        class="bg-transparent text-xs text-slate-200 font-semibold focus:outline-none cursor-pointer max-w-[180px] truncate"
      >
        {#if $registeredModels.length === 0}
          <option value="">No models registered</option>
        {:else}
          {#each $registeredModels as m}
            <option value={m.id}>
              {m.display_name} {m.vision_supported ? '👁️' : ''}
            </option>
          {/each}
        {/if}
      </select>

      {#if selectedDropdownModelId && selectedDropdownModelId !== $activeModelId}
        <button
          on:click={applyModelSwitch}
          disabled={isSwitching}
          class="ml-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-[11px] font-bold rounded text-white transition animate-pulse"
        >
          {isSwitching ? 'Loading...' : 'Apply'}
        </button>
      {/if}
    </div>

    <!-- Persona Selector -->
    <div class="flex items-center gap-2 bg-slate-800/80 border border-slate-700/80 rounded-lg px-2.5 py-1">
      <span class="text-xs text-slate-400 font-medium">Persona:</span>
      <select
        bind:value={$activeCharacterId}
        class="bg-transparent text-xs text-slate-200 font-semibold focus:outline-none cursor-pointer"
      >
        {#each $characters as c}
          <option value={c.id}>{c.avatar_emoji} {c.name}</option>
        {/each}
      </select>
    </div>


  </div>

  <div class="flex items-center gap-3">
    <!-- Live VRAM Status Pill -->
    {#if $supervisorStatus?.vram}
      <div class="hidden xl:flex items-center gap-2 px-2.5 py-1 bg-slate-800/50 border border-slate-700/60 rounded-lg text-[11px] font-mono text-slate-300">
        <span class="h-2 w-2 rounded-full {$supervisorStatus.state === 'Ready' ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
        <span>VRAM: {($supervisorStatus.vram.used_mb / 1024).toFixed(1)} / {($supervisorStatus.vram.allowed_ceiling_mb / 1024).toFixed(1)} GB</span>
      </div>
    {/if}

    <button
      on:click={exportMarkdown}
      disabled={!$activeConversationId}
      class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700/80 text-xs text-slate-300 rounded-lg transition disabled:opacity-40 flex items-center gap-1.5"
    >
      📥 Export (.md)
    </button>
  </div>
</header>
