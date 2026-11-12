<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import PodcastTab from './voice/PodcastTab.svelte';
  import SttTab from './voice/SttTab.svelte';
  import TtsTab from './voice/TtsTab.svelte';
  import WaveformMonitor from './voice/WaveformMonitor.svelte';

  let currentSubTab: 'tts' | 'podcast' | 'stt' = 'tts';
  let audioPlayer: HTMLAudioElement;
  let isAudioActive = false;
  let audioStatusText = 'Idle';
  let engineStatus: { stt_available: boolean; tts_available: boolean } | null = null;

  function handleAudioState(active: boolean, status: string) {
    isAudioActive = active;
    audioStatusText = status;
  }

  onMount(async () => {
    try {
      const res = await apiFetch('/media/audio/status');
      if (res.ok) engineStatus = await res.json();
    } catch {}
  });
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-6 max-w-4xl bg-[var(--bg-base)]">
  <div class="flex items-center justify-between pb-4 border-b border-[var(--border-color)]">
    <div>
      <h2 class="text-xl font-bold text-[var(--text-main)]">🎙️ Voice Studio Pro</h2>
      {#if engineStatus}
        <div class="flex items-center gap-2 mt-1 text-xs">
          <span class={`px-2 py-0.5 rounded-full font-mono text-[10px] font-semibold ${engineStatus.tts_available ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-500'}`}>
            Kokoro: {engineStatus.tts_available ? 'Ready' : 'Unavailable'}
          </span>
          <span class={`px-2 py-0.5 rounded-full font-mono text-[10px] font-semibold ${engineStatus.stt_available ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-500'}`}>
            Whisper: {engineStatus.stt_available ? 'Ready' : 'Unavailable'}
          </span>
        </div>
      {/if}
    </div>

    <!-- Sub-Tab Navigation -->
    <div class="flex gap-1.5 bg-[var(--bg-card)] p-1 rounded-xl border border-[var(--border-color)]">
      <button on:click={() => (currentSubTab = 'tts')} class={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${currentSubTab === 'tts' ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-muted)]'}`}>Speech Synthesis</button>
      <button on:click={() => (currentSubTab = 'podcast')} class={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${currentSubTab === 'podcast' ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-muted)]'}`}>Podcast Studio</button>
      <button on:click={() => (currentSubTab = 'stt')} class={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${currentSubTab === 'stt' ? 'bg-[var(--accent)] text-white' : 'text-[var(--text-muted)]'}`}>Transcription (STT)</button>
    </div>
  </div>

  <audio bind:this={audioPlayer} class="hidden"></audio>

  <!-- Waveform Monitor -->
  <WaveformMonitor isActive={isAudioActive} statusText={audioStatusText} />

  <!-- Sub-Tabs -->
  {#if currentSubTab === 'tts'}
    <TtsTab {audioPlayer} onPlayStateChange={handleAudioState} />
  {:else if currentSubTab === 'podcast'}
    <PodcastTab {audioPlayer} onPlayStateChange={handleAudioState} />
  {:else if currentSubTab === 'stt'}
    <SttTab onRecordStateChange={handleAudioState} />
  {/if}
</div>
