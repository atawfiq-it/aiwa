<script lang="ts">
  import { apiFetch } from '../../lib/api';

  let hfQuery = 'qwen2.5-vl';
  let hfResults: any[] = [];
  let isSearching = false;
  let selectedFiles: any = null;

  async function search() {
    isSearching = true;
    selectedFiles = null;
    try {
      const res = await apiFetch(`/hf/search?query=${encodeURIComponent(hfQuery)}`);
      if (res.ok) hfResults = await res.json();
    } finally {
      isSearching = false;
    }
  }

  async function inspect(repoId: string) {
    const res = await apiFetch(`/hf/models/${encodeURIComponent(repoId)}/files`);
    if (res.ok) selectedFiles = await res.json();
  }

  async function download(repoId: string, filename: string, mmproj: string | null) {
    await apiFetch('/hf/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_id: repoId, filename, mmproj_filename: mmproj }),
    });
    alert(`Download queued for ${filename}! Check Task dashboard.`);
  }
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-5xl">
  <div>
    <h2 class="text-xl font-bold">HuggingFace GGUF & Vision Hub</h2>
    <p class="text-xs text-slate-400 mt-1">Discover, download, and auto-register local GGUF models.</p>
  </div>

  <div class="flex gap-2 max-w-xl">
    <input type="text" bind:value={hfQuery} on:keydown={(e) => e.key === 'Enter' && search()} class="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2 text-sm text-slate-200 focus:outline-none" />
    <button on:click={search} disabled={isSearching} class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-lg">
      {isSearching ? 'Searching...' : 'Search'}
    </button>
  </div>

  <div class="grid grid-cols-2 gap-4">
    {#each hfResults as m}
      <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl flex flex-col justify-between space-y-3">
        <div>
          <div class="flex items-center gap-2">
            <span class="font-bold text-sm text-indigo-400">{m.name}</span>
            {#if m.is_vision}<span class="px-2 py-0.5 bg-indigo-950 border border-indigo-700 text-indigo-300 rounded text-[10px]">👁️ Vision</span>{/if}
          </div>
          <p class="text-xs text-slate-500 mt-0.5">{m.repo_id}</p>
        </div>
        <button on:click={() => inspect(m.repo_id)} class="w-full py-1.5 bg-slate-800 hover:bg-slate-700 rounded text-xs">Inspect Files</button>
      </div>
    {/each}
  </div>

  {#if selectedFiles}
    <div class="bg-slate-900 border border-indigo-900/60 p-6 rounded-xl space-y-3">
      <h3 class="text-sm font-bold text-slate-200">Files in `{selectedFiles.repo_id}`:</h3>
      {#each selectedFiles.gguf_files as file}
        <div class="flex items-center justify-between p-2 bg-slate-800/60 rounded text-xs">
          <span class="font-mono">{file}</span>
          <button on:click={() => download(selectedFiles.repo_id, file, selectedFiles.mmproj_files[0] || null)} class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 font-semibold rounded">Download</button>
        </div>
      {/each}
    </div>
  {/if}
</div>
