<script lang="ts">
  import { apiFetch } from '../../../lib/api';

  export let onRecordStateChange: (recording: boolean, label: string) => void;

  let isRecording = false;
  let isTranscribing = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];
  let transcriptData: any = null;

  async function handleAudioUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file, file.name);

    isTranscribing = true;
    onRecordStateChange(true, `Transcribing ${file.name}...`);

    try {
      const res = await apiFetch('/media/audio/transcribe-direct', { method: 'POST', body: formData });
      if (res.ok) {
        transcriptData = await res.json();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Transcription failed: ${err.detail || 'Server error'}`);
      }
    } catch (err: any) {
      alert(`Network error: ${err.message}`);
    } finally {
      isTranscribing = false;
      onRecordStateChange(false, 'Idle');
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
      isRecording = false;
      onRecordStateChange(false, 'Idle');
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
          isTranscribing = true;
          onRecordStateChange(true, 'Transcribing microphone audio...');

          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', blob, 'microphone_rec.webm');

          try {
            const res = await apiFetch('/media/audio/transcribe-direct', { method: 'POST', body: formData });
            if (res.ok) {
              transcriptData = await res.json();
            } else {
              const err = await res.json().catch(() => ({}));
              alert(`Transcription failed: ${err.detail || 'Server error'}`);
            }
          } catch (err: any) {
            alert(`Transcription error: ${err.message}`);
          } finally {
            isTranscribing = false;
            onRecordStateChange(false, 'Idle');
          }

          stream.getTracks().forEach((t) => t.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        onRecordStateChange(true, '🎤 Recording Microphone');
      } catch (err: any) {
        alert(`Microphone access error: ${err.message}. Please check browser/system microphone permissions.`);
        isRecording = false;
        onRecordStateChange(false, 'Idle');
      }
    }
  }

  function downloadSRT() {
    if (!transcriptData) return;
    let srt = '';
    if (transcriptData.segments && transcriptData.segments.length > 0) {
      transcriptData.segments.forEach((seg: any, idx: number) => {
        const formatTime = (sec: number) => {
          const date = new Date(sec * 1000);
          const hh = String(Math.floor(sec / 3600)).padStart(2, '0');
          const mm = String(date.getUTCMinutes()).padStart(2, '0');
          const ss = String(date.getUTCSeconds()).padStart(2, '0');
          const ms = String(date.getUTCMilliseconds()).padStart(3, '0');
          return `${hh}:${mm}:${ss},${ms}`;
        };
        srt += `${idx + 1}\n${formatTime(seg.start)} --> ${formatTime(seg.end)}\n${seg.text}\n\n`;
      });
    } else {
      srt = `1\n00:00:00,000 --> 00:00:05,000\n${transcriptData.text || ''}\n`;
    }

    const blob = new Blob([srt], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'transcript.srt';
    a.click();
  }
</script>

<div class="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4 shadow-sm select-none">
  <div>
    <h3 class="text-sm font-bold text-[var(--text-main)]">Speech to Text & Captioning (Faster-Whisper)</h3>
    <p class="text-xs text-[var(--text-muted)] mt-0.5">Record speech from your microphone or upload any audio file to transcribe with automatic timestamps.</p>
  </div>

  <div class="flex items-center gap-3 pt-2">
    <!-- Push-to-Talk Mic Recording Button -->
    <button
      type="button"
      on:click={toggleRecording}
      disabled={isTranscribing}
      class={`px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition ${
        isRecording ? 'bg-rose-600 animate-pulse text-white shadow-lg shadow-rose-600/30' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md'
      }`}
    >
      {#if isTranscribing}
        <span class="animate-spin">🌀</span> Transcribing audio...
      {:else if isRecording}
        ⏹️ Stop Recording
      {:else}
        🎤 Start Microphone
      {/if}
    </button>

    <!-- Upload Audio File Button -->
    <label class="px-4 py-2.5 bg-[var(--bg-base)] border border-[var(--border-color)] hover:opacity-80 rounded-xl text-xs font-semibold cursor-pointer text-[var(--text-main)] transition flex items-center gap-2">
      📁 Upload Audio File
      <input
        type="file"
        accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm"
        on:change={handleAudioUpload}
        disabled={isRecording || isTranscribing}
        class="hidden"
      />
    </label>

    {#if transcriptData}
      <button
        type="button"
        on:click={downloadSRT}
        class="px-4 py-2.5 bg-[var(--bg-base)] border border-[var(--border-color)] text-xs font-semibold rounded-xl hover:opacity-80 transition text-[var(--text-main)] flex items-center gap-1.5 ml-auto"
      >
        📥 Download Subtitles (.SRT)
      </button>
    {/if}
  </div>

  {#if transcriptData}
    <div class="p-4 bg-[var(--bg-base)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-main)] font-mono leading-relaxed space-y-2">
      <div class="flex items-center justify-between border-b border-[var(--border-color)] pb-2 text-[var(--text-muted)]">
        <span class="font-bold">Detected Language: {transcriptData.language?.toUpperCase() || 'EN'}</span>
        {#if transcriptData.duration}
          <span>Duration: {transcriptData.duration.toFixed(1)}s</span>
        {/if}
      </div>
      <p class="whitespace-pre-wrap select-text">{transcriptData.text}</p>
    </div>
  {/if}
</div>
