<script lang="ts">
  import { apiFetch } from '../../../lib/api';

  export let audioPlayer: HTMLAudioElement;
  export let onPlayStateChange: (playing: boolean, label: string) => void;

  let ttsText = '';
  let selectedVoice = 'af_heart';
  let speechSpeed = 1.0;
  let isSpeaking = false;

  async function generateSpeech() {
    if (!ttsText.trim() || isSpeaking) return;
    isSpeaking = true;
    onPlayStateChange(true, '🔊 Synthesizing / Playing');

    try {
      const res = await apiFetch('/media/audio/speech-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ttsText, voice: selectedVoice, speed: speechSpeed }),
      });

      if (res.ok) {
        const blob = await res.blob();
        audioPlayer.src = URL.createObjectURL(blob);
        audioPlayer.play();
        audioPlayer.onpause = () => {
          isSpeaking = false;
          onPlayStateChange(false, 'Idle');
        };
        audioPlayer.onended = () => {
          isSpeaking = false;
          onPlayStateChange(false, 'Idle');
        };
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`TTS Error: ${err.detail || 'Service unavailable'}`);
        isSpeaking = false;
        onPlayStateChange(false, 'Idle');
      }
    } catch (e: any) {
      alert(`Network Error: ${e.message}`);
      isSpeaking = false;
      onPlayStateChange(false, 'Idle');
    }
  }
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
  <h3 class="text-sm font-bold text-[var(--text-main)]">Single Voice Synthesis (Kokoro)</h3>
  <textarea
    rows="4"
    bind:value={ttsText}
    placeholder="Enter any text to synthesize aloud..."
    class="w-full bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl p-3 text-xs text-[var(--text-main)] focus:outline-none"
  ></textarea>

  <div class="grid grid-cols-3 gap-4 items-center">
    <div>
      <label for="voice-picker" class="text-xs font-semibold text-[var(--text-muted)] block mb-1">Voice Profile:</label>
      <select id="voice-picker" bind:value={selectedVoice} class="w-full bg-[var(--bg-base)] text-[var(--text-main)] border border-[var(--border-color)] rounded-lg p-2 text-xs">
        <option value="af_heart">Heart (US Warm Female)</option>
        <option value="am_adam">Adam (US Deep Male)</option>
        <option value="bf_emma">Emma (UK Professional Female)</option>
      </select>
    </div>

    <div>
      <div class="flex justify-between text-xs text-[var(--text-muted)] mb-1">
        <span>Speed Multiplier:</span>
        <span class="font-mono font-bold text-[var(--accent)]">{speechSpeed.toFixed(2)}x</span>
      </div>
      <input type="range" min="0.75" max="1.5" step="0.05" bind:value={speechSpeed} class="w-full accent-indigo-600 cursor-pointer" />
    </div>

    <div class="flex justify-end pt-4">
      <button
        on:click={generateSpeech}
        disabled={isSpeaking || !ttsText.trim()}
        class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white rounded-xl shadow-md transition"
      >
        {isSpeaking ? 'Playing...' : '🔊 Synthesize & Play'}
      </button>
    </div>
  </div>
</div>
