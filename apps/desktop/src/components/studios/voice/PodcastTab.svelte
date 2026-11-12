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

  async function handleCsvUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const text = await file.text();
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
    const parsedTurns: { speaker: string; voice: string; text: string }[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      // Skip header
      if (i === 0 && line.toLowerCase().includes('speaker')) continue;

      // Handle simple CSV splitting
      const parts = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/).map((p) => p.replace(/^"|"$/g, '').trim());
      if (parts.length >= 3) {
        parsedTurns.push({ speaker: parts[0], voice: parts[1], text: parts[2] });
      } else if (parts.length === 2) {
        parsedTurns.push({
          speaker: parts[0],
          voice: parts[0].toLowerCase().includes('host') ? 'am_adam' : 'bf_emma',
          text: parts[1],
        });
      }
    }

    if (parsedTurns.length > 0) {
      podcastTurns = parsedTurns;
      alert(`Imported ${parsedTurns.length} dialogue turns from ${file.name}!`);
    } else {
      alert('Could not parse dialogue rows. Format: speaker,voice,text');
    }
  }

  function downloadSampleCsv() {
    const sample = `speaker,voice,text\nAdam (Host),am_adam,"Welcome to AIWA Workstation Podcast Episode 1."\nEmma (Guest),bf_emma,"Glad to be here. Today we are testing multi-line synthesis from CSV."\nAdam (Host),am_adam,"How does Kokoro process long paragraphs without crashing?"\nEmma (Guest),bf_emma,"It concatenates audio buffers seamlessly into a single master track."\n`;
    const blob = new Blob([sample], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'podcast_template.csv';
    a.click();
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
    <div class="flex items-center gap-2">
      <button
        type="button"
        on:click={downloadSampleCsv}
        class="px-2.5 py-1.5 bg-[var(--bg-base)] text-xs font-semibold rounded-lg border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-main)]"
        title="Download sample CSV template"
      >
        📄 Template
      </button>

      <label class="px-3 py-1.5 bg-[var(--bg-base)] text-xs font-semibold rounded-lg border border-[var(--border-color)] text-[var(--text-main)] cursor-pointer hover:opacity-80 transition flex items-center gap-1.5">
        📁 Import CSV
        <input type="file" accept=".csv" on:change={handleCsvUpload} class="hidden" />
      </label>

      <button
        type="button"
        on:click={addLine}
        class="px-3 py-1.5 bg-[var(--bg-base)] text-xs font-semibold rounded-lg border border-[var(--border-color)] text-[var(--text-main)] hover:opacity-80"
      >
        + Add Line
      </button>
    </div>
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
