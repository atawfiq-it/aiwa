<script lang="ts">
  import { apiFetch } from '../../lib/api';

  export let isStreaming: boolean;
  export let onSendMessage: (text: string, files: string[]) => void;

  let promptText = '';
  let attachedFiles: { name: string; path: string; type: string }[] = [];
  let isRecording = false;
  let mediaRecorder: MediaRecorder | null = null;
  let audioChunks: Blob[] = [];

  async function handleFileUpload(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files) return;

    for (const f of Array.from(input.files)) {
      const formData = new FormData();
      formData.append('file', f);
      const res = await apiFetch('/files/upload', { method: 'POST', body: formData });
      if (res.ok) {
        const data = await res.json();
        attachedFiles = [...attachedFiles, { name: data.file_name, path: data.file_path, type: data.mime_type }];
      }
    }
  }

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorder?.stop();
      isRecording = false;
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
          const blob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', blob, 'recording.webm');
          const res = await apiFetch('/media/audio/transcribe-direct', { method: 'POST', body: formData });
          if (res.ok) {
            const data = await res.json();
            promptText = promptText ? `${promptText} ${data.text}` : data.text;
          }
          stream.getTracks().forEach((t) => t.stop());
        };
        mediaRecorder.start();
        isRecording = true;
      } catch (err) {
        alert('Microphone access denied: ' + err);
      }
    }
  }

  function submit() {
    if ((!promptText.trim() && attachedFiles.length === 0) || isStreaming) return;
    const imgPaths = attachedFiles.filter((f) => f.type.startsWith('image/')).map((f) => f.path);
    onSendMessage(promptText, imgPaths);
    promptText = '';
    attachedFiles = [];
  }
</script>

<div class="p-4 border-t border-slate-800 bg-slate-950">
  {#if attachedFiles.length > 0}
    <div class="flex flex-wrap gap-2 mb-2">
      {#each attachedFiles as file, i}
        <div class="flex items-center gap-1.5 bg-slate-800 border border-slate-700 px-2.5 py-1 rounded-md text-xs text-slate-300">
          <span>{file.type.startsWith('image/') ? '🖼️' : '📄'}</span>
          <span class="truncate max-w-[200px]">{file.name}</span>
          <button on:click={() => (attachedFiles = attachedFiles.filter((_, idx) => idx !== i))} class="hover:text-rose-400">✕</button>
        </div>
      {/each}
    </div>
  {/if}

  <div class="flex items-center gap-2">
    <label class="p-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg cursor-pointer transition" title="Attach Media">
      📎 <input type="file" accept="image/*,application/pdf" multiple on:change={handleFileUpload} class="hidden" />
    </label>

    <button on:click={toggleRecording} class={`p-2.5 rounded-lg border transition ${isRecording ? 'bg-rose-600 animate-pulse text-white' : 'bg-slate-800 border-slate-700 text-slate-300'}`} title="Push-to-Talk">
      🎤
    </button>

    <input
      type="text"
      bind:value={promptText}
      on:keydown={(e) => e.key === 'Enter' && submit()}
      placeholder={isRecording ? 'Listening...' : 'Type message, describe image, or speak...'}
      disabled={isStreaming}
      class="flex-1 bg-slate-800 text-slate-100 rounded-lg px-4 py-2.5 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
    />

    <button on:click={submit} disabled={isStreaming || (!promptText.trim() && attachedFiles.length === 0)} class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm font-semibold rounded-lg transition">
      Send
    </button>
  </div>
</div>
