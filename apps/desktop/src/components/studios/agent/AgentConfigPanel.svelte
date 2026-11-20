<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../../lib/api';
  import {
    activeModelId,
    registeredModels,
    supervisorStatus,
  } from '../../../lib/stores';
  import SandboxFileExplorer from './SandboxFileExplorer.svelte';

  export let agents: any[] = [];
  export let selectedAgentId: string = '';
  export let promptText: string = '';
  export let requireApproval: boolean = false;
  export let isRunning: boolean = false;
  export let currentRunId: string | null = null;
  export let onLaunch: () => void;
  export let onLoadRun: (run: any) => void;

  let selectedDropdownModelId = $activeModelId;
  let isSwitchingModel = false;
  let savedRuns: any[] = [];

  // Renaming state
  let editingRunId: string | null = null;
  let editingRunTitle = '';

  $: if ($activeModelId && !selectedDropdownModelId) {
    selectedDropdownModelId = $activeModelId;
  }

  // Automatically refresh saved runs when an agent finishes executing
  $: if (!isRunning) {
    loadSavedRuns();
  }

  async function loadSavedRuns() {
    try {
      const res = await apiFetch('/agents/runs/history');
      if (res.ok) savedRuns = await res.json();
    } catch {}
  }

  async function applyModelSwitch() {
    if (!selectedDropdownModelId || selectedDropdownModelId === $activeModelId) return;
    isSwitchingModel = true;
    try {
      const res = await apiFetch(`/models/${selectedDropdownModelId}/load`, { method: 'POST' });
      if (res.ok) {
        $activeModelId = selectedDropdownModelId;
        const statusRes = await apiFetch('/models/status');
        if (statusRes.ok) $supervisorStatus = await statusRes.json();
      }
    } finally {
      isSwitchingModel = false;
    }
  }

  function startRename(run: any, e: Event) {
    e.stopPropagation();
    editingRunId = run.id;
    editingRunTitle = run.title;
  }

  async function saveRename(runId: string, e: Event) {
    e.stopPropagation();
    if (!editingRunTitle.trim()) return;
    try {
      const res = await apiFetch(`/agents/runs/${runId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editingRunTitle.trim() }),
      });
      if (res.ok) {
        const updated = await res.json();
        savedRuns = savedRuns.map((r) => (r.id === runId ? { ...r, title: updated.title } : r));
      }
    } finally {
      editingRunId = null;
    }
  }

  async function deleteRun(runId: string, e: Event) {
    e.stopPropagation();
    if (!confirm('Permanently delete this agent task and its workspace files?')) return;
    try {
      const res = await apiFetch(`/agents/runs/${runId}`, { method: 'DELETE' });
      if (res.ok) {
        savedRuns = savedRuns.filter((r) => r.id !== runId);
      }
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  onMount(loadSavedRuns);
</script>

<div class="w-96 border-r border-[var(--border-color)] p-6 flex flex-col justify-between overflow-y-auto space-y-6 bg-[var(--bg-card)] select-none shrink-0 shadow-sm">
  <div class="space-y-4">
    <div>
      <h2 class="text-base font-bold text-[var(--text-main)]">🤖 Agent Studio Pro</h2>
      <p class="text-[11px] text-[var(--text-muted)]">Visual DAG reasoning, sandbox breakpoints & task records.</p>
    </div>

    <!-- Model Selector with Live Status Pill -->
    <div>
      <div class="flex items-center justify-between mb-1">
        <div class="flex items-center gap-2">
          <label for="agent-model-select" class="text-xs font-semibold text-[var(--text-muted)]">Active Model:</label>
          {#if $supervisorStatus}
            <span class={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${
              $supervisorStatus.state === 'Ready'
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
            }`}>
              {$supervisorStatus.state === 'Ready' ? 'Ready' : 'Standby'}
            </span>
          {/if}
        </div>

        {#if selectedDropdownModelId && selectedDropdownModelId !== $activeModelId}
          <button
            type="button"
            on:click={applyModelSwitch}
            disabled={isSwitchingModel}
            class="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-[10px] font-bold text-white rounded-md transition animate-pulse"
          >
            {isSwitchingModel ? '...' : 'Apply Switch'}
          </button>
        {/if}
      </div>

      <select
        id="agent-model-select"
        bind:value={selectedDropdownModelId}
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-main)] font-semibold focus:outline-none"
      >
        {#if $registeredModels.length === 0}
          <option value="">No models registered</option>
        {:else}
          {#each $registeredModels as m}
            <option value={m.id}>
              {m.display_name} {m.vision_supported ? '👁️' : ''} {m.id === $activeModelId ? '(Active)' : ''}
            </option>
          {/each}
        {/if}
      </select>
    </div>

    <!-- Scenario Agent Picker -->
    <div>
      <label for="agent-picker" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Scenario Agent:</label>
      <select
        id="agent-picker"
        bind:value={selectedAgentId}
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-main)] font-semibold focus:outline-none"
      >
        {#each agents as a}
          <option value={a.id}>{a.name}</option>
        {/each}
      </select>
    </div>

    <!-- Human Breakpoint Switch -->
    <label class="flex items-center gap-2 text-xs text-[var(--text-main)] cursor-pointer select-none">
      <input type="checkbox" bind:checked={requireApproval} class="rounded accent-indigo-600 cursor-pointer" />
      <span>Pause for Approval before Code Execution (HITL)</span>
    </label>

    <!-- Task Prompt Textarea -->
    <div>
      <label for="task-prompt" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Task Assignment / Code to Review:</label>
      <textarea
        id="task-prompt"
        rows="4"
        bind:value={promptText}
        placeholder="Describe task or paste Python code to audit..."
        class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs font-mono text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
      ></textarea>
    </div>

    <!-- Conditional Sandbox Files (Hidden unless files exist) -->
    <SandboxFileExplorer activeRunId={currentRunId} />

    <!-- Saved Task Records List -->
    {#if savedRuns.length > 0}
      <div class="pt-3 border-t border-[var(--border-color)] space-y-2">
        <h4 class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">Saved Task Records ({savedRuns.length})</h4>
        <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
          {#each savedRuns as run}
            <div
              role="button"
              tabindex="0"
              on:click={() => onLoadRun(run)}
              on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && onLoadRun(run)}
              class="group flex items-center justify-between p-2 bg-[var(--bg-base)] hover:bg-[var(--border-color)]/50 rounded-xl text-xs border border-[var(--border-color)] cursor-pointer transition"
            >
              {#if editingRunId === run.id}
                <input
                  type="text"
                  bind:value={editingRunTitle}
                  on:keydown={(e) => e.key === 'Enter' && saveRename(run.id, e)}
                  class="flex-1 bg-[var(--bg-card)] text-xs text-[var(--text-main)] rounded px-1.5 py-0.5 border border-indigo-500 focus:outline-none"
                />
                <button type="button" on:click={(e) => saveRename(run.id, e)} class="text-indigo-400 hover:text-indigo-300 ml-1 px-1">✓</button>
              {:else}
                <span class="truncate flex-1 mr-2 text-[var(--text-main)] font-medium">{run.title}</span>
                <div class="opacity-0 group-hover:opacity-100 flex items-center gap-1">
                  <button type="button" on:click={(e) => startRename(run, e)} class="text-slate-400 hover:text-slate-200 p-0.5" title="Rename Task">✏️</button>
                  <button type="button" on:click={(e) => deleteRun(run.id, e)} class="text-slate-400 hover:text-rose-400 p-0.5" title="Delete Task">✕</button>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <!-- Launch Button -->
  <button
    type="button"
    on:click={onLaunch}
    disabled={isRunning || !promptText.trim() || $registeredModels.length === 0}
    class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-xs font-bold text-white rounded-xl shadow-md transition flex items-center justify-center gap-2"
  >
    {#if $registeredModels.length === 0}
      ⚠️ No Models Registered
    {:else if isRunning}
      <span class="animate-spin">🌀</span> Agent Reasoning...
    {:else}
      🚀 Launch Autonomous Agent
    {/if}
  </button>
</div>