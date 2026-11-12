<script lang="ts">
  import { apiFetch } from '../../../lib/api';

  export let audioPlayer: HTMLAudioElement;
  export let onPlayStateChange: (playing: boolean, label: string) => void;

  let podcastTurns: { speaker: string; voice: string; text: string }[] = [
    { speaker: 'Adam (Host)', voice: 'am_adam', text: 'Welcome to AIWA Studio. Today we are discussing quantum computing.' },
    { speaker: 'Emma (Guest)', voice: 'bf_emma', text: 'Thanks Adam. What is most exciting is running models privately on edge hardware.' },
  ];
  let isGeneratingPodcast = false;
  let podcastAudioUrl = '';

  async function generatePodcast() {
    if (isGeneratingPodcast) return;
    isGeneratingPodcast = true;
    onPlayStateChange(true, '🎙️ Rendering Podcast');

    try {
      const res = await apiFetch('/media/audio/podcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: podcastTurns, speed: 1.0 }),
      });

      if (res.ok) {
        const blob = await res.blob();
        podcastAudioUrl = URL.createObjectURL(blob);
        audioPlayer.src = podcastAudioUrl;
        audioPlayer.play();
        audioPlayer.onpause = () => {
          isGeneratingPodcast = false;
          onPlayStateChange(false, 'Idle');
        };
        audioPlayer.onended = () => {
          isGeneratingPodcast = false;
          onPlayStateChange(false, 'Idle');
        };
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Podcast Error: ${err.detail || 'Failed generation'}`);
        isGeneratingPodcast = false;
        onPlayStateChange(false, 'Idle');
      }
    } catch (e: any) {
      alert(`Network Error: ${e.message}`);
      isGeneratingPodcast = false;
      onPlayStateChange(false, 'Idle');
    }
  }

  function addLine() {
    podcastTurns = [...podcastTurns, { speaker: 'Speaker', voice: 'am_adam', text: '' }];
  }

  function removeLine(idx: number) {
    podcastTurns = podcastTurns.filter((_, i) => i !== idx);
  }
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
  <div class="flex items-center justify-between">
    <div>
      <h3 class="text-sm font-bold text-[var(--text-main)]">Dual-Speaker Podcast Generator</h3>
      <p class="text-xs text-[var(--text-muted)]">Alternating dialogue synthesized and merged into a continuous master episode.</p>
    </div>
    <button on:click={addLine} class="px-3 py-1.5 bg-[var(--bg-base)] text-xs font-semibold rounded-lg border border-[var(--border-color)] text-[var(--text-main)]">+ Add Line</button>
  </div>

  <div class="space-y-3 max-h-96 overflow-y-auto pr-1">
    {#each podcastTurns as turn, i}
      <div class="p-3 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl flex items-center gap-3">
        <input type="text" bind:value={turn.speaker} placeholder="Speaker Name" class="w-28 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-1.5 text-xs text-[var(--text-main)] font-bold" />
        <select bind:value={turn.voice} class="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-1.5 text-xs text-[var(--text-main)]">
          <option value="am_adam">Adam (US Male)</option>
          <option value="bf_emma">Emma (UK Female)</option>
          <option value="af_heart">Heart (US Female)</option>
        </select>
        <input type="text" bind:value={turn.text} placeholder="Spoken dialogue..." class="flex-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-1.5 text-xs text-[var(--text-main)]" />
        <button on:click={() => removeLine(i)} class="text-slate-400 hover:text-rose-400 p-1">✕</button>
      </div>
    {/each}
  </div>

  <div class="flex justify-between items-center pt-2">
    {#if podcastAudioUrl}
      <a href={podcastAudioUrl} download="podcast_episode.wav" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white rounded-xl">💾 Download Episode (.WAV)</a>
    {:else}
      <div></div>
    {/if}
    <button on:click={generatePodcast} disabled={isGeneratingPodcast} class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-xs font-bold text-white rounded-xl shadow-md transition">
      {isGeneratingPodcast ? 'Rendering Episode...' : '🎙️ Generate Master Podcast'}
    </button>
  </div>
</div>
