<script lang="ts">
  import { apiFetch } from '../../lib/api';

  let ttsText = '';
  let selectedVoice = 'af_heart';
  let isSpeaking = false;
  let audioPlayer: HTMLAudioElement;

  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let transcribedText = '';

  async function generateSpeech() {
    if (!ttsText.trim()) return;
    isSpeaking = true;
    try {
      const res = await apiFetch('/media/audio/speech-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: ttsText, voice: selectedVoice }),
      });
      if (res.ok) {
        const blob = await res.blob();
        audioPlayer.src = URL.createObjectURL(blob);
        audioPlayer.play();
      }
    } finally {
      isSpeaking = false;
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorder?.stop();
      isRecording = false;
    } else {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('file', blob, 'rec.webm');
        const res = await apiFetch('/media/audio/transcribe-direct', { method: 'POST', body: formData });
        if (res.ok) {
          const data = await res.json();
          transcribedText = data.text;
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
      isRecording = true;
    }
  }
</script>

<div class="flex-1 p-8 overflow-y-auto space-y-8 max-w-4xl bg-slate-900">
  <div>
    <h2 class="text-xl font-bold text-slate-100">🎙️ Voice Studio (Kokoro & Faster-Whisper)</h2>
    <p class="text-xs text-slate-400 mt-1">Runs 100% on CPU — Zero VRAM competition with graphics or language models.</p>
  </div>

  <audio bind:this={audioPlayer} class="hidden"></audio>

  <!-- Text-to-Speech -->
  <div class="bg-slate-950 border border-slate-800 p-6 rounded-2xl space-y-4">
    <h3 class="text-sm font-bold text-indigo-400">1. Text to Spoken Audio (Kokoro TTS)</h3>
    <textarea rows="3" bind:value={ttsText} placeholder="Type any text to speak aloud..." class="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 focus:outline-none"></textarea>

    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <label for="voice-select" class="text-xs text-slate-400">Voice Persona:</label>
        <select id="voice-select" bind:value={selectedVoice} class="bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200">
          <option value="af_heart">Heart (US Warm Female)</option>
          <option value="am_adam">Adam (US Deep Male)</option>
          <option value="bf_emma">Emma (UK Professional Female)</option>
        </select>
      </div>

      <button on:click={generateSpeech} disabled={isSpeaking || !ttsText.trim()} class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-semibold rounded-lg text-white">
        {isSpeaking ? 'Synthesizing...' : '🔊 Synthesize & Play'}
      </button>
    </div>
  </div>

  <!-- Speech-to-Text -->
  <div class="bg-slate-950 border border-slate-800 p-6 rounded-2xl space-y-4">
    <h3 class="text-sm font-bold text-indigo-400">2. Speech to Text (Faster-Whisper)</h3>
    <p class="text-xs text-slate-400">Speak into your microphone to transcribe audio with automatic punctuation.</p>

    <div class="flex items-center gap-3">
      <button on:click={toggleRecording} class={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${isRecording ? 'bg-rose-600 animate-pulse text-white' : 'bg-slate-800 text-slate-300'}`}>
        🎤 {isRecording ? 'Stop Recording' : 'Start Microphone'}
      </button>
    </div>

    {#if transcribedText}
      <div class="p-4 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 font-mono">
        <span class="text-slate-500 block mb-1">Transcript:</span>
        {transcribedText}
      </div>
    {/if}
  </div>
</div>
