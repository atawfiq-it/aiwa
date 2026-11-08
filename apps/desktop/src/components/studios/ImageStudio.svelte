<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';

  let checkpoints: { name: string; path: string; size_gb: number }[] = [];
  let selectedCheckpoint = '';
  let promptText = '';
  let negativePrompt = 'ugly, blurry, distorted, bad anatomy';
  let width = 512;
  let height = 512;
  let steps = 4;
  let isGenerating = false;
  let currentImage: any = null;
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
    if (res.ok) history = await res.json();
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
        currentImage = await res.json();
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

  onMount(() => {
    loadCheckpoints();
    loadHistory();
  });
</script>

<div class="flex-1 flex overflow-hidden bg-slate-900">
  <!-- Controls Panel (Left) -->
  <div class="w-96 border-r border-slate-800 p-6 flex flex-col justify-between overflow-y-auto space-y-6">
    <div class="space-y-4">
      <div>
        <h2 class="text-base font-bold text-slate-100">🎨 Image Studio</h2>
        <p class="text-[11px] text-slate-400">Direct FP16 diffusion with 100% GPU VRAM.</p>
      </div>

      <!-- Checkpoint Dropdown -->
      <div>
        <label for="checkpoint-select" class="text-xs font-semibold text-slate-300 block mb-1">Model Checkpoint:</label>
        <select
          id="checkpoint-select"
          bind:value={selectedCheckpoint}
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
        >
          {#if checkpoints.length === 0}
            <option value="">No .safetensors checkpoints detected</option>
          {:else}
            {#each checkpoints as ckpt}
              <option value={ckpt.path}>{ckpt.name} ({ckpt.size_gb} GB)</option>
            {/each}
          {/if}
        </select>
      </div>

      <!-- Prompt -->
      <div>
        <label for="prompt-input" class="text-xs font-semibold text-slate-300 block mb-1">Prompt:</label>
        <textarea
          id="prompt-input"
          rows="3"
          bind:value={promptText}
          placeholder="Describe your visual concept..."
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-100 focus:outline-none focus:border-indigo-500"
        ></textarea>
      </div>

      <!-- Negative Prompt -->
      <div>
        <label for="neg-prompt-input" class="text-xs font-semibold text-slate-300 block mb-1">Negative Prompt:</label>
        <input
          id="neg-prompt-input"
          type="text"
          bind:value={negativePrompt}
          class="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-xs text-slate-300 focus:outline-none"
        />
      </div>

      <!-- Aspect Ratio Pills -->
      <div>
        <label class="text-xs font-semibold text-slate-300 block mb-1.5">Dimensions:</label>
        <div class="grid grid-cols-3 gap-2">
          <button
            on:click={() => { width = 512; height = 512; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 512 && height === 512 ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
          >
            512×512
          </button>
          <button
            on:click={() => { width = 768; height = 512; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 768 && height === 512 ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
          >
            768×512
          </button>
          <button
            on:click={() => { width = 1024; height = 1024; }}
            class={`py-1.5 rounded-lg text-xs font-mono border transition ${width === 1024 && height === 1024 ? 'bg-indigo-600 border-indigo-500 text-white' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
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
        <p class="text-[10px] text-slate-500 mt-0.5">Use 1–4 steps for Turbo/Lightning, 15–20 for standard SD1.5.</p>
      </div>
    </div>

    <!-- Render Button -->
    <button
      on:click={generate}
      disabled={isGenerating || !promptText.trim() || !selectedCheckpoint}
      class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white rounded-xl transition shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
    >
      {#if isGenerating}
        <span class="animate-spin">🌀</span> Rendering on GPU...
      {:else}
        ✨ Render Artwork
      {/if}
    </button>
  </div>

  <!-- Canvas & Preview (Right) -->
  <div class="flex-1 flex flex-col justify-between p-8 overflow-y-auto">
    <!-- Active Canvas -->
    <div class="flex-1 flex items-center justify-center border-2 border-dashed border-slate-800 rounded-2xl p-6 min-h-[420px]">
      {#if isGenerating}
        <div class="text-center space-y-3">
          <div class="h-12 w-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-sm font-semibold text-slate-300">Rendering directly on GPU...</p>
          <p class="text-xs text-slate-500">Allocating 100% VRAM to diffusers</p>
        </div>
      {:else if currentImage}
        <div class="text-center space-y-4 max-w-lg">
          <img
            src={currentImage.image_url}
            alt="Rendered Art"
            class="rounded-xl shadow-2xl max-h-[500px] object-contain mx-auto border border-slate-700"
          />
          <div class="flex justify-center gap-3">
            <a
              href={currentImage.image_url}
              download={currentImage.file_name}
              class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold rounded-lg text-white transition flex items-center gap-1.5"
            >
              💾 Download Image
            </a>
          </div>
        </div>
      {:else}
        <div class="text-center text-slate-500 space-y-2">
          <span class="text-4xl">🎨</span>
          <p class="text-sm">Ready to generate art</p>
          <p class="text-xs text-slate-600">Pick a checkpoint, type your prompt, and click Render.</p>
        </div>
      {/if}
    </div>

    <!-- Gallery History -->
    {#if history.length > 0}
      <div class="mt-8 space-y-3">
        <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Recent Creations</h3>
        <div class="grid grid-cols-6 gap-3">
          {#each history.slice(0, 6) as item}
            <div
              on:click={() => (currentImage = { image_url: `http://127.0.0.1:8000/api/v1/media/files/${item.id}`, file_name: item.file_name })}
              class="aspect-square bg-slate-800 rounded-lg overflow-hidden cursor-pointer border border-slate-700/60 hover:border-indigo-500 transition"
            >
              <img src={`http://127.0.0.1:8000/api/v1/media/files/${item.id}`} alt="Thumb" class="w-full h-full object-cover" />
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
