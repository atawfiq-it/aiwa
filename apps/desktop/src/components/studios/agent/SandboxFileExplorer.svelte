<script lang="ts">
  import { apiFetch } from '../../../lib/api';


  export let activeRunId: string | null = null;
  let files: { name: string; size_bytes: number; modified: string }[] = [];

  $: if (activeRunId) {
    loadFiles(activeRunId);
  } else {
    files = [];
  }

  async function loadFiles(runId: string) {
    try {
      const res = await apiFetch(`/agents/workspaces/${runId}/files`);
      if (res.ok) files = await res.json();
    } catch {
      files = [];
    }
  }

</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-4 space-y-3 select-none shadow-sm">
  <div class="flex items-center justify-between">
    <h4 class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">📁 Sandbox Workspace Files</h4>
    <button type="button" on:click={() => activeRunId && loadFiles(activeRunId)} class="text-xs text-[var(--accent)] hover:opacity-80">Refresh</button>
  </div>

  <!-- Completely hidden unless files are actually present -->
{#if files.length > 0}
  <div class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-4 space-y-3 select-none shadow-sm mt-3">
    <div class="flex items-center justify-between">
      <h4 class="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">📁 Workspace Files ({files.length})</h4>
      <button type="button" on:click={() => activeRunId && loadFiles(activeRunId)} class="text-xs text-[var(--accent)] hover:opacity-80">Refresh</button>
    </div>

    <div class="space-y-1.5 font-mono text-xs max-h-36 overflow-y-auto">
      {#each files as f}
        <div class="flex items-center justify-between p-2 bg-[var(--bg-base)] rounded-lg border border-[var(--border-color)]">
          <span class="text-[var(--text-main)] truncate max-w-[200px]">{f.name}</span>
          <span class="text-[10px] text-[var(--text-muted)]">{(f.size_bytes / 1024).toFixed(1)} KB</span>
        </div>
      {/each}
    </div>
  </div>
{/if}
</div>
