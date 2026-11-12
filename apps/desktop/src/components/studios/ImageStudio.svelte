<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import { sessionToken } from '../../lib/stores';

  let checkpoints: { name: string; path: string; size_gb: number; folder: string }[] = [];
  let selectedCheckpoint = '';
  let promptText = '';
  let negativePrompt = 'ugly, blurry, distorted, bad anatomy, low quality';
  let width = 512;
  let height = 512;
  let steps = 25;
  let guidanceScale = 7.0;
  let sampler = 'DPM++ 2M Karras';
  let seed = -1;
  let batchSize = 1;
  let stylePreset = 'cinematic';

  let isGenerating = false;
  let currentArtifacts: { file_id: string; file_name: string; image_url: string }[] = [];
  let usedSeed: number | null = null;
  let history: any[] = [];

  const samplers = ['DPM++ 2M Karras', 'Euler a', 'Euler', 'DDIM'];
  const styles = [
    { id: 'none', label: 'None' },
    { id: 'cinematic', label: '🎬 Cinematic' },
    { id: 'photorealistic', label: '📷 Photorealistic' },
    { id: 'digital_art', label: '🎨 Digital Art' },
    { id: 'anime', label: '✨ Anime' },
    { id: 'fantasy', label: '🐉 Fantasy Art' },
  ];

  async function loadCheckpoints() {
    const res = await apiFetch('/media/diffusion/checkpoints');
    if (res.ok) {
      checkpoints = await res.json();
      if (checkpoints.length > 0 && !selectedCheckpoint) {
        selectedCheckpoint = checkpoints[0].path;
      }
    }
  }

  async function loadHistory() {
    const res = await apiFetch('/media/gallery');
    if (res.ok) history = await res.json();
  }

  async function generate() {
    if (!promptText.trim() || !selectedCheckpoint || isGenerating) return;
    isGenerating = true;
    currentArtifacts = [];

    try {
      const res = await apiFetch('/media/diffusion/generate-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptText,
          negative_prompt: negativePrompt,
          checkpoint_path: selectedCheckpoint,
          width,
          height,
          steps,
          guidance_scale: guidanceScale,
          sampler,
          seed,
          batch_size: batchSize,
          style_preset: stylePreset,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        currentArtifacts = data.artifacts;
        usedSeed = data.seed;
        loadHistory();
      } else {
        const err = await res.json();
        alert(`Generation failed: ${err.detail}`);
      }
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      isGenerating = false;
    }
  }

  async function deleteImage(fileId: string) {
    if (!confirm('Are you sure you want to permanently delete this image from your disk?')) return;
    try {
      const res = await apiFetch(`/media/files/${fileId}`, { method: 'DELETE' });
      if (res.ok) {
        history = history.filter((item) => item.id !== fileId);
        currentArtifacts = currentArtifacts.filter((item) => item.file_id !== fileId);
      }
    } catch (e: any) {
      alert(`Deletion failed: ${e.message}`);
    }
  }

  onMount(() => {
    loadCheckpoints();
    loadHistory();
  });
</script>

<div class="flex-1 flex overflow-hidden bg-[var(--bg-base)]">
  <!-- Controls Panel (Left) -->
  <div class="w-[420px] bg-[var(--bg-card)] border-r border-[var(--border-color)] p-6 flex flex-col justify-between overflow-y-auto space-y-6 shrink-0 select-none shadow-sm">
    <div class="space-y-5">
      <div>
        <h2 class="text-base font-bold text-[var(--text-main)]">🎨 Pro Diffusion Studio</h2>
        <p class="text-[11px] text-[var(--text-muted)]">High-precision denoising, custom samplers & seed control.</p>
      </div>

      <!-- Checkpoint Dropdown -->
      <div>
        <label for="checkpoint-select" class="text-xs font-semibold text-[var(--text-main)] block mb-1">Model Checkpoint:</label>
        <select
          id="checkpoint-select"
          bind:value={selectedCheckpoint}
          class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2.5 text-xs text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)] font-mono"
        >
          {#each checkpoints as ckpt}
            <option value={ckpt.path}>[{ckpt.folder}] {ckpt.name} ({ckpt.size_gb} GB)</option>
          {/each}
        </select>
      </div>

      <!-- Style Preset Pills -->
      <div>
        <span class="text-xs font-semibold text-[var(--text-main)] block mb-1.5">Style Preset:</span>
        <div class="grid grid-cols-3 gap-1.5">
          {#each styles as style}
            <button
              type="button"
              on:click={() => (stylePreset = style.id)}
              class={`py-1.5 px-2 rounded-lg text-[11px] font-semibold border transition truncate ${
                stylePreset === style.id
                  ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                  : 'bg-[var(--bg-base)] border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-main)]'
              }`}
            >
              {style.label}
            </button>
          {/each}
        </div>
      </div>

      <!-- Prompt -->
      <div>
        <label for="prompt-input" class="text-xs font-semibold text-[var(--text-main)] block mb-1">Prompt:</label>
        <textarea
          id="prompt-input"
          rows="3"
          bind:value={promptText}
          placeholder="Describe your subject and scene in detail..."
          class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs text-[var(--text-main)] focus:outline-none focus:border-[var(--accent)]"
        ></textarea>
      </div>

      <!-- Negative Prompt -->
      <div>
        <label for="neg-prompt-input" class="text-xs font-semibold text-[var(--text-main)] block mb-1">Negative Prompt:</label>
        <input
          id="neg-prompt-input"
          type="text"
          bind:value={negativePrompt}
          class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2 text-xs text-[var(--text-muted)] focus:outline-none"
        />
      </div>

      <!-- Sampler & Batch Size -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label for="sampler-select" class="text-xs font-semibold text-[var(--text-main)] block mb-1">Sampler:</label>
          <select
            id="sampler-select"
            bind:value={sampler}
            class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2 text-xs text-[var(--text-main)] focus:outline-none font-semibold"
          >
            {#each samplers as s}
              <option value={s}>{s}</option>
            {/each}
          </select>
        </div>

        <div>
          <label for="batch-select" class="text-xs font-semibold text-[var(--text-main)] block mb-1">Batch Count:</label>
          <select
            id="batch-select"
            bind:value={batchSize}
            class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2 text-xs text-[var(--text-main)] focus:outline-none"
          >
            <option value={1}>1 Image</option>
            <option value={2}>2 Images</option>
            <option value={4}>4 Images</option>
          </select>
        </div>
      </div>

      <!-- Sliders: Steps & CFG -->
      <div class="space-y-3 p-3 bg-[var(--bg-base)] rounded-xl border border-[var(--border-color)]">
        <div>
          <div class="flex justify-between text-xs text-[var(--text-main)] mb-1">
            <span>Sampling Steps:</span>
            <span class="font-mono text-indigo-500 font-bold">{steps}</span>
          </div>
          <input type="range" min="1" max="50" bind:value={steps} class="w-full accent-indigo-600 cursor-pointer" />
          <p class="text-[10px] text-[var(--text-muted)]">20–30 steps recommended for crisp details.</p>
        </div>

        <div>
          <div class="flex justify-between text-xs text-[var(--text-main)] mb-1">
            <span>CFG Guidance Scale:</span>
            <span class="font-mono text-indigo-500 font-bold">{guidanceScale.toFixed(1)}</span>
          </div>
          <input type="range" min="1" max="15" step="0.5" bind:value={guidanceScale} class="w-full accent-indigo-600 cursor-pointer" />
          <p class="text-[10px] text-[var(--text-muted)]">7.0 standard for SD 1.5; 1.5–2.0 for Turbo/Lightning.</p>
        </div>
      </div>

      <!-- Seed Control -->
      <div>
        <div class="flex justify-between items-center text-xs text-[var(--text-main)] mb-1">
          <span class="font-semibold">Seed:</span>
          {#if usedSeed !== null && seed === -1}
            <span class="text-[10px] font-mono text-[var(--text-muted)]">Used: {usedSeed}</span>
          {/if}
        </div>
        <div class="flex gap-2">
          <input
            type="number"
            bind:value={seed}
            placeholder="-1 for random seed"
            class="flex-1 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-2 text-xs font-mono text-[var(--text-main)] focus:outline-none"
          />
          <button
            type="button"
            on:click={() => (seed = -1)}
            class="px-3 py-1.5 bg-[var(--bg-base)] hover:opacity-80 border border-[var(--border-color)] rounded-xl text-xs font-semibold"
            title="Random Seed"
          >
            🎲 Random
          </button>
        </div>
      </div>
    </div>

    <!-- Render Button -->
    <button
      type="button"
      on:click={generate}
      disabled={isGenerating || !promptText.trim() || !selectedCheckpoint}
      style="background-color: var(--accent); color: var(--accent-text);"
      class="w-full py-3.5 disabled:opacity-50 text-xs font-bold rounded-xl transition shadow-lg flex items-center justify-center gap-2 mt-4"
    >
      {#if isGenerating}
        <span class="animate-spin">🌀</span> Denoising on GPU ({steps} steps)...
      {:else}
        ✨ Render Artwork ({batchSize}x)
      {/if}
    </button>
  </div>

  <!-- Canvas & Gallery (Right) -->
  <div class="flex-1 flex flex-col justify-between p-8 overflow-y-auto">
    <!-- Active Generation Canvas -->
    <div class="flex-1 flex items-center justify-center border-2 border-dashed border-[var(--border-color)] rounded-2xl p-6 min-h-[440px] bg-[var(--bg-card)] shadow-sm">
      {#if isGenerating}
        <div class="text-center space-y-3">
          <div class="h-12 w-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-sm font-semibold text-[var(--text-main)]">Executing {sampler} ({steps} steps)...</p>
          <p class="text-xs text-[var(--text-muted)]">Generating with full GPU allocation</p>
        </div>
      {:else if currentArtifacts.length > 0}
        <div class="w-full space-y-4">
          <!-- Grid for batch renders -->
          <div class={`grid gap-4 mx-auto max-w-4xl ${currentArtifacts.length === 1 ? 'grid-cols-1 max-w-lg' : currentArtifacts.length === 2 ? 'grid-cols-2' : 'grid-cols-2'}`}>
            {#each currentArtifacts as art}
              <div class="space-y-2 text-center group">
                <img
                  src={`${art.image_url}?token=${$sessionToken}`}
                  alt={art.file_name}
                  class="rounded-xl shadow-xl max-h-[460px] object-contain mx-auto border border-[var(--border-color)] bg-black/10"
                />
                <div class="flex items-center justify-center gap-2 mt-2">
                  <a
                    href={`${art.image_url}?token=${$sessionToken}`}
                    download={art.file_name}
                    class="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-md transition"
                  >
                    💾 Download ({art.file_name})
                  </a>
                  <button
                      type="button"
                      on:click={() => deleteImage(art.file_id)}
                      class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 border border-rose-500/30 rounded-xl text-xs font-semibold transition"
                      title="Delete image permanently"
                    >
                      🗑️ Delete
                    </button>
                  </div>
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="text-center text-[var(--text-muted)] space-y-2 select-none">
          <span class="text-4xl">🎨</span>
          <p class="text-sm font-medium text-[var(--text-main)]">Ready for high-fidelity generation</p>
          <p class="text-xs">Pick a checkpoint, select a style, and click Render.</p>
        </div>
      {/if}
    </div>

    <!-- Recent Creations Gallery -->
    {#if history.length > 0}
      <div class="mt-8 space-y-3">
        <h3 class="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">Recent Creations</h3>
        <div class="grid grid-cols-8 gap-3">
          {#each history.slice(0, 8) as item}
            <div class="relative group aspect-square rounded-xl overflow-hidden border border-[var(--border-color)]">
              <button
                type="button"
                on:click={() => (currentArtifacts = [{ file_id: item.id, file_name: item.file_name, image_url: `http://127.0.0.1:8000/api/v1/media/files/${item.id}` }])}
                class="w-full h-full"
              >
                <img
                  src={`http://127.0.0.1:8000/api/v1/media/files/${item.id}?token=${$sessionToken}`}
                  alt="Thumbnail"
                  class="w-full h-full object-cover"
                />
              </button>
              <button
                type="button"
                on:click={() => deleteImage(item.id)}
                class="absolute top-1 right-1 opacity-0 group-hover:opacity-100 p-1 bg-black/70 hover:bg-rose-600 text-white rounded-lg text-[10px] transition"
                title="Delete from disk"
              >
                ✕
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
