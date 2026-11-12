<script lang="ts">
  import { apiFetch } from '../../../lib/api';

  export let onRecordStateChange: (recording: boolean, label: string) => void;

  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let transcriptData: any = null;

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorder?.stop();
      isRecording = false;
      onRecordStateChange(false, 'Idle');
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
          transcriptData = await res.json();
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
      isRecording = true;
      onRecordStateChange(true, '🎤 Recording Microphone');
    }
  }

  function downloadSRT() {
    if (!transcriptData) return;
    const srt = `1\n00:00:00,000 --> 00:00:05,000\n${transcriptData.text || ''}\n`;
    const blob = new Blob([srt], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcript.srt';
    a.click();
  }
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm">
  <h3 class="text-sm font-bold text-[var(--text-main)]">Speech to Text & Captioning (Faster-Whisper)</h3>
  <p class="text-xs text-[var(--text-muted)]">Record speech directly and download synchronized subtitle files.</p>

  <div class="flex items-center gap-3">
    <button on:click={toggleRecording} class={`px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition ${isRecording ? 'bg-rose-600 animate-pulse text-white' : 'bg-indigo-600 text-white'}`}>
      🎤 {isRecording ? 'Stop Recording' : 'Start Recording'}
    </button>

    {#if transcriptData}
      <button on:click={downloadSRT} class="px-4 py-2.5 bg-[var(--bg-base)] border border-[var(--border-color)] text-xs font-semibold rounded-xl text-[var(--text-main)]">
        📥 Download Subtitles (.SRT)
      </button>
    {/if}
  </div>

  {#if transcriptData}
    <div class="p-4 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-main)] font-mono leading-relaxed">
      <span class="text-[var(--text-muted)] block mb-1 font-bold">Transcript:</span>
      {transcriptData.text}
    </div>
  {/if}
</div>
