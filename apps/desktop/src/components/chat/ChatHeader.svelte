<script lang="ts">
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeModelId,
    characters,
    registeredModels,
    supervisorStatus,
  } from '../../lib/stores';

  export let isPersonaPanelOpen: boolean = true;

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
</script>

<header class="h-14 border-b border-[var(--border-color)] px-6 flex items-center justify-between bg-[var(--bg-card)] select-none shadow-sm">
  <div class="flex items-center gap-3">
    <!-- Model Selector -->
    <div class="flex items-center gap-2 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl px-3 py-1.5">
      <span class="text-xs text-[var(--text-muted)] font-medium">Model:</span>
      <select
        bind:value={selectedDropdownModelId}
        class="bg-transparent text-xs text-[var(--text-main)] font-semibold focus:outline-none cursor-pointer max-w-[200px] truncate"
      >
        {#if $registeredModels.length === 0}
          <option value="">No models registered</option>
        {:else}
          {#each $registeredModels as m}
            <option value={m.id}>{m.display_name} {m.vision_supported ? '👁️' : ''}</option>
          {/each}
        {/if}
      </select>

      {#if selectedDropdownModelId && selectedDropdownModelId !== $activeModelId}
        <button
          type="button"
          on:click={applyModelSwitch}
          disabled={isSwitching}
          class="ml-1 px-2.5 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-[11px] font-bold rounded-lg text-white transition animate-pulse"
        >
          {isSwitching ? '...' : 'Apply'}
        </button>
      {/if}
    </div>

    <!-- Persona Selector (No Emojis) -->
    <div class="flex items-center gap-2 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl px-3 py-1.5">
      <span class="text-xs text-[var(--text-muted)] font-medium">Persona:</span>
      <select
        bind:value={$activeCharacterId}
        class="bg-transparent text-xs text-[var(--text-main)] font-semibold focus:outline-none cursor-pointer"
      >
        {#each $characters as c}
          <option value={c.id}>{c.name}</option>
        {/each}
      </select>
    </div>
  </div>

  <div class="flex items-center gap-3">
    <!-- Live VRAM Gauge -->
    {#if $supervisorStatus?.vram}
      <div class="hidden xl:flex items-center gap-2 px-3 py-1 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl text-[11px] font-mono text-[var(--text-muted)]">
        <span class="h-2 w-2 rounded-full {$supervisorStatus.state === 'Ready' ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
        <span>VRAM: {($supervisorStatus.vram.used_mb / 1024).toFixed(1)} / {($supervisorStatus.vram.allowed_ceiling_mb / 1024).toFixed(1)} GB</span>
      </div>
    {/if}

    <!-- Toggle Persona Panel Button (Re-opens when closed) -->
    <button
      type="button"
      on:click={() => (isPersonaPanelOpen = !isPersonaPanelOpen)}
      class={`px-3 py-1.5 border rounded-xl text-xs font-semibold flex items-center gap-1.5 transition ${
        isPersonaPanelOpen
          ? 'bg-indigo-600/10 text-indigo-400 border-indigo-500/40'
          : 'bg-[var(--bg-base)] text-[var(--text-muted)] border-[var(--border-color)] hover:text-[var(--text-main)]'
      }`}
      title="Toggle Persona Panel"
    >
      <span>👤</span> Persona Profile
    </button>
  </div>
</header>
