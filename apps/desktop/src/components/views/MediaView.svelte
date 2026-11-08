<script lang="ts">
  import { apiFetch } from '../../lib/api';

  let imagePrompt = '';
  let gallery: any[] = [];
  let isGenerating = false;

  async function loadGallery() {
    const res = await apiFetch('/media/gallery');
    if (res.ok) gallery = await res.json();
  }

  async function generateImage() {
    if (!imagePrompt.trim()) return;
    isGenerating = true;
    try {
      await apiFetch('/media/images/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: imagePrompt, steps: 4 }),
      });
      imagePrompt = '';
      alert('Image generation queued via ComfyUI! Check Task Dashboard.');
    } finally {
      isGenerating = false;
    }
  }

  loadGallery();
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-5xl">
  <div>
    <h2 class="text-xl font-bold text-slate-100">Media Studio (ComfyUI Fast-Diffusion)</h2>
    <p class="text-xs text-slate-400 mt-1">Render digital art via embedded SDXL-Turbo / DreamShaper Lightning checkpoints.</p>
  </div>

  <div class="flex gap-2 max-w-2xl">
    <input type="text" bind:value={imagePrompt} placeholder="Describe the scene to render..." class="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 focus:outline-none" />
    <button on:click={generateImage} disabled={isGenerating} class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 font-semibold text-xs rounded-lg text-white transition">
      {isGenerating ? 'Dispatching...' : 'Generate Image'}
    </button>
  </div>

  <div class="space-y-4">
    <h3 class="text-sm font-semibold text-slate-300">Generated Media Gallery ({gallery.length})</h3>
    <div class="grid grid-cols-3 gap-4">
      {#each gallery as item}
        <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden p-3 space-y-2">
          <p class="text-xs text-slate-300 truncate font-semibold">{item.prompt || item.file_name}</p>
          <p class="text-[10px] text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
        </div>
      {/each}
    </div>
  </div>
</div>
