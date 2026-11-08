<!-- apps/desktop/src/components/studios/ImageStudio.svelte -->
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
  let steps = 4;
  let isGenerating = false;
  let currentImage: { image_url: string; file_name: string; file_id?: string } | null = null;
  let history: any[] = [];

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
    if (res.ok) {
      history = await res.json();
      // If no image is currently displayed, preview the latest creation
      if (!currentImage && history.length > 0) {
        currentImage = {
          image_url: `http://127.0.0.1:8000/api/v1/media/files/${history[0].id}?token=${$sessionToken}`,
          file_name: history[0].file_name,
          file_id: history[0].id,
        };
      }
    }
  }

  async function generate() {
    if (!promptText.trim() || !selectedCheckpoint) return;
    isGenerating = true;
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
          guidance_scale: steps <= 4 ? 1.0 : 7.0, // 1.0 for Turbo/Lightning, 7.0 for SD1.5
        }),
      });

      if (res.ok) {
        const data = await res.json();
        currentImage = {
          file_name: data.file_name,
          file_id: data.file_id,
          image_url: `${data.image_url}?token=${$sessionToken}`,
        };
        await loadHistory();
      } else {
        const err = await res.json();
        alert(`Generation failed: ${err.detail || 'Unknown error'}`);
      }
    } catch (e: any) {
      alert(`Error connecting to backend: ${e.message}`);
    } finally {
      isGenerating = false;
    }
  }

  onMount(() => {
    loadCheckpoints();
    loadHistory();
  });
</script>

<div class="flex-1 flex overflow-hidden bg-slate-900">
  <!-- Controls Sidebar (Left) -->
  <div class="w-96 border-r border-slate-800 p-6 flex flex-col justify-between overflow-y-auto space-y-6 select-none">
    <div class="space-y-5">
      <div>
        <h2 class="text-base font-bold text-slate-100 flex items-center gap-2">
          <span>🎨</span> Image Studio
        </h2>
        <p class="text-[11px] text-slate-400 mt-0.5">Direct PyTorch FP16 diffusion with 100% dedicated GPU VRAM.</p>
      </div>

      <!-- Checkpoint Selector -->
      <div>
        <label for="checkpoint-select" class="text-xs font-semibold text-slate-300 block mb-1">Model Checkpoint (.safetensors):</label>
        <select
          id="checkpoint-select"
          bind:value={selectedCheckpoint}
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
        >
          {#if checkpoints.length === 0}
            <option value="">No checkpoints detected. Check DIFFUSION_MODEL_DIRECTORIES in .env</option>
          {:else}
            {#each checkpoints as ckpt}
              <option value={ckpt.path}>
                [{ckpt.folder}] {ckpt.name} — {ckpt.size_gb} GB
              </option>
            {/each}
          {/if}
        </select>
      </div>

      <!-- Prompt Input -->
      <div>
        <label for="prompt-input" class="text-xs font-semibold text-slate-300 block mb-1">Prompt:</label>
        <textarea
          id="prompt-input"
          rows="3"
          bind:value={promptText}
          placeholder="Describe your visual concept in detail..."
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
        ></textarea>
      </div>

      <!-- Negative Prompt Input -->
      <div>
        <label for="neg-prompt-input" class="text-xs font-semibold text-slate-300 block mb-1">Negative Prompt:</label>
        <input
          id="neg-prompt-input"
          type="text"
          bind:value={negativePrompt}
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-300 focus:outline-none"
        />
      </div>

      <!-- Dimension Selector -->
      <div>
        <label class="text-xs font-semibold text-slate-300 block mb-1.5">Resolution:</label>
        <div class="grid grid-cols-3 gap-2">
          <button
            type="button"
            on:click={() => { width = 512; height = 512; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 512 && height === 512 ? 'bg-indigo-600 border-indigo-500 text-white font-bold' : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'}`}
          >
            512×512
          </button>
          <button
            type="button"
            on:click={() => { width = 768; height = 512; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 768 && height === 512 ? 'bg-indigo-600 border-indigo-500 text-white font-bold' : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'}`}
          >
            768×512
          </button>
          <button
            type="button"
            on:click={() => { width = 1024; height = 1024; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 1024 && height === 1024 ? 'bg-indigo-600 border-indigo-500 text-white font-bold' : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'}`}
          >
            1024×1024
          </button>
        </div>
      </div>

      <!-- Steps Slider -->
      <div>
        <div class="flex justify-between text-xs text-slate-300 mb-1">
          <span>Inference Steps:</span>
          <span class="font-mono text-indigo-400 font-bold">{steps}</span>
        </div>
        <input type="range" min="1" max="25" bind:value={steps} class="w-full accent-indigo-600 cursor-pointer" />
        <div class="flex justify-between text-[10px] text-slate-500 mt-1 font-mono">
          <span>1-4 (Turbo/Lightning)</span>
          <span>15-20 (SD 1.5)</span>
        </div>
      </div>
    </div>

    <!-- Render Button -->
    <button
      on:click={generate}
      disabled={isGenerating || !promptText.trim() || !selectedCheckpoint}
      class="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white rounded-xl transition shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer"
    >
      {#if isGenerating}
        <span class="animate-spin text-base">🌀</span> Rendering on GPU...
      {:else}
        ✨ Render Artwork
      {/if}
    </button>
  </div>

  <!-- Canvas Display & Gallery (Right) -->
  <div class="flex-1 flex flex-col justify-between p-8 overflow-y-auto">
    <!-- Active Art Canvas -->
    <div class="flex-1 flex items-center justify-center border-2 border-dashed border-slate-800/80 rounded-2xl p-6 min-h-[460px] bg-slate-950/40">
      {#if isGenerating}
        <div class="text-center space-y-3">
          <div class="h-12 w-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-sm font-semibold text-slate-200">Rendering directly on GPU...</p>
          <p class="text-xs text-slate-500 font-mono">diffusers.from_single_file(torch.float16)</p>
        </div>
      {:else if currentImage}
        <div class="text-center space-y-4 max-w-2xl">
          <img
            src={currentImage.image_url}
            alt="Rendered Art"
            class="rounded-2xl shadow-2xl max-h-[500px] max-w-full object-contain mx-auto border border-slate-700/80"
          />
          <div class="flex justify-center gap-3">
            <a
              href={currentImage.image_url}
              download={currentImage.file_name}
              class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-xl text-white transition flex items-center gap-2 shadow-lg shadow-indigo-600/20"
            >
              💾 Download Image
            </a>
          </div>
        </div>
      {:else}
        <div class="text-center text-slate-500 space-y-2 select-none">
          <span class="text-5xl block">🎨</span>
          <p class="text-sm font-medium">Ready to create</p>
          <p class="text-xs text-slate-600">Select your checkpoint, type a prompt, and click Render.</p>
        </div>
      {/if}
    </div>

    <!-- Recent Creations Gallery -->
    {#if history.length > 0}
      <div class="mt-8 space-y-3">
        <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider select-none">Recent Creations</h3>
        <div class="grid grid-cols-8 gap-3">
          {#each history.slice(0, 8) as item}
            <div
              on:click={() => (currentImage = {
                image_url: `http://127.0.0.1:8000/api/v1/media/files/${item.id}?token=${$sessionToken}`,
                file_name: item.file_name,
                file_id: item.id
              })}
              class="aspect-square bg-slate-800 rounded-xl overflow-hidden cursor-pointer border border-slate-700/60 hover:border-indigo-500 transition shadow group relative"
            >
              <img
                src={`http://127.0.0.1:8000/api/v1/media/files/${item.id}?token=${$sessionToken}`}
                alt="Creation Thumbnail"
                class="w-full h-full object-cover group-hover:scale-105 transition duration-300"
              />
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
