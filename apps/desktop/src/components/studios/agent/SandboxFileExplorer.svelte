<script lang="ts">
  import { apiFetch } from '../../../lib/api';


  export let activeRunId: string | null = null;

  let files: { name: string; size_bytes: number; modified: string }[] = [];

  $: if (activeRunId) {
    loadFiles(activeRunId);
  }

  async function loadFiles(runId: string) {
    try {
      const res = await apiFetch(`/agents/workspaces/${runId}/files`);
      if (res.ok) files = await res.json();
    } catch {}
  }


  function round(num: number, decimals: number) {
    const factor = 10 ** decimals;
    return Math.round(num * factor) / factor;
  }
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-4 space-y-3 select-none shadow-sm">
  <div class="flex items-center justify-between">
    <h4 class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">📁 Sandbox Workspace Files</h4>
    <button type="button" on:click={() => activeRunId && loadFiles(activeRunId)} class="text-xs text-[var(--accent)] hover:opacity-80">Refresh</button>
  </div>

  {#if files.length === 0}
    <p class="text-xs text-[var(--text-muted)] italic">No artifacts generated in this run.</p>
  {:else}
    <div class="space-y-1.5 font-mono text-xs">
      {#each files as f}
        <div class="flex items-center justify-between p-2 bg-[var(--bg-base)] rounded-lg border border-[var(--border-color)]">
          <span class="text-[var(--text-main)] truncate max-w-[200px]">{f.name}</span>
          <span class="text-[10px] text-[var(--text-muted)]">{round(f.size_bytes / 1024, 1)} KB</span>
        </div>
      {/each}
    </div>
  {/if}
</div>
