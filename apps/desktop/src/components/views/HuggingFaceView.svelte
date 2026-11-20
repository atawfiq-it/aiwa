<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';

  let galleryPresets: any[] = [];
  let hfQuery = 'qwen2.5-vl';
  let hfResults: any[] = [];
  let isSearching = false;
  let selectedFiles: any = null;

  async function loadGalleryPresets() {
    try {
      const res = await apiFetch('/models/gallery');
      if (res.ok) galleryPresets = await res.json();
    } catch {}
  }

  async function installPreset(presetId: string, name: string) {
    const res = await apiFetch(`/models/gallery/${presetId}/install`, { method: 'POST' });
    if (res.ok) {
      alert(`Installing '${name}' in the background! Track progress in ⚡ Tasks.`);
    } else {
      const err = await res.json().catch(() => ({}));
      alert(`Install blocked: ${err.detail || 'Incompatible hardware'}`);
    }
  }

  async function search() {
    if (!hfQuery.trim()) return;
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
    alert(`Download queued for ${filename}! Check the ⚡ Tasks dashboard.`);
  }

  onMount(loadGalleryPresets);
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-5xl bg-[var(--bg-base)]">
  <div>
    <h2 class="text-xl font-bold text-[var(--text-main)]">🌐 Model Gallery & HuggingFace Hub</h2>
    <p class="text-xs text-[var(--text-muted)] mt-1">Install curated YAML presets with one click or search HuggingFace Hub for custom GGUF models.</p>
  </div>

  <!-- Section 1: Curated YAML Model Gallery -->
  {#if galleryPresets.length > 0}
    <div class="space-y-3 pb-6 border-b border-[var(--border-color)]">
      <div>
        <h3 class="text-sm font-bold text-[var(--text-main)]">⚡ Curated One-Click Model Gallery</h3>
        <p class="text-xs text-[var(--text-muted)]">Pre-tuned context lengths, vision projectors, and hardware compatibility verified.</p>
      </div>

      <div class="grid grid-cols-2 gap-4">
        {#each galleryPresets as preset}
          <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-2xl flex flex-col justify-between space-y-3 shadow-sm">
            <div>
              <div class="flex items-center justify-between gap-2">
                <span class="font-bold text-sm text-[var(--text-main)]">{preset.name}</span>
                <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-base)] border border-[var(--border-color)] text-[var(--text-muted)]">
                  ~{preset.min_vram_gb} GB RAM
                </span>
              </div>
              <p class="text-xs text-[var(--text-muted)] mt-1">{preset.description}</p>
              <div class="flex flex-wrap gap-1.5 mt-2">
                {#each preset.tags as tag}
                  <span class="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded text-[10px] font-semibold">{tag}</span>
                {/each}
              </div>
            </div>

            {#if preset.installed}
              <div class="w-full py-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-500 text-center rounded-xl text-xs font-bold">
                ✅ Installed & Ready
              </div>
            {:else if !preset.compatible}
              <div class="w-full py-1.5 bg-slate-500/10 border border-slate-500/20 text-slate-400 text-center rounded-xl text-xs font-medium">
                Unavailable on this OS
              </div>
            {:else}
              <button
                type="button"
                on:click={() => installPreset(preset.id, preset.name)}
                class="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition shadow-sm"
              >
                ⬇️ Install & Auto-Configure
              </button>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Section 2: Open HuggingFace GGUF Search -->
  <div class="space-y-4">
    <div>
      <h3 class="text-sm font-bold text-[var(--text-main)]">🔍 Search HuggingFace Hub</h3>
      <p class="text-xs text-[var(--text-muted)]">Search live repositories for GGUF weights and vision projectors.</p>
    </div>

    <div class="flex gap-2 max-w-xl">
      <input
        type="text"
        bind:value={hfQuery}
        on:keydown={(e) => e.key === 'Enter' && search()}
        placeholder="Search GGUF models (e.g. qwen2.5-vl, llama-3.2)..."
        class="flex-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl px-4 py-2 text-sm text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
      />
      <button
        type="button"
        on:click={search}
        disabled={isSearching}
        class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition"
      >
        {isSearching ? 'Searching...' : 'Search Hub'}
      </button>
    </div>

    <div class="grid grid-cols-2 gap-4">
      {#each hfResults as m}
        <div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 rounded-2xl flex flex-col justify-between space-y-3 shadow-sm">
          <div>
            <div class="flex items-center gap-2">
              <span class="font-bold text-sm text-indigo-400 truncate">{m.name}</span>
              {#if m.is_vision}
                <span class="px-2 py-0.5 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 rounded text-[10px] font-semibold">👁️ Vision</span>
              {/if}
            </div>
            <p class="text-xs text-[var(--text-muted)] mt-0.5">{m.repo_id}</p>
          </div>
          <button
            type="button"
            on:click={() => inspect(m.repo_id)}
            class="w-full py-1.5 bg-[var(--bg-base)] hover:opacity-80 border border-[var(--border-color)] text-[var(--text-main)] rounded-xl text-xs font-medium transition"
          >
            Inspect Quantizations & Files
          </button>
        </div>
      {/each}
    </div>

    {#if selectedFiles}
      <div class="bg-[var(--bg-card)] border-2 border-indigo-500/40 p-6 rounded-2xl space-y-3 shadow-md">
        <h3 class="text-sm font-bold text-[var(--text-main)]">Files in `{selectedFiles.repo_id}`:</h3>
        <div class="space-y-2 max-h-60 overflow-y-auto pr-1">
          {#each selectedFiles.gguf_files as file}
            <div class="flex items-center justify-between p-2.5 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl text-xs">
              <span class="font-mono text-[var(--text-main)]">{file}</span>
              <button
                type="button"
                on:click={() => download(selectedFiles.repo_id, file, selectedFiles.mmproj_files[0] || null)}
                class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition"
              >
                Download
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>