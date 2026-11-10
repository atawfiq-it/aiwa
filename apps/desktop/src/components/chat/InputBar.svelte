<script lang="ts">
  import { apiFetch } from '../../lib/api';

  export let isStreaming: boolean;
  export let onSendMessage: (text: string, files: string[]) => void;
  export let onStopGeneration: () => void;

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
          promptText = promptText ? `${promptText} ${data.text}` : data.text;
        }
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorder.start();
      isRecording = true;
    }
  }

  function submit() {
    if (isStreaming) {
      onStopGeneration();
      return;
    }
    if (!promptText.trim() && attachedFiles.length === 0) return;
    const imgPaths = attachedFiles.filter((f) => f.type.startsWith('image/')).map((f) => f.path);
    onSendMessage(promptText, imgPaths);
    promptText = '';
    attachedFiles = [];
  }
</script>

<div class="p-4 border-t border-[var(--border-color)] bg-[var(--bg-card)]">
  {#if attachedFiles.length > 0}
    <div class="flex flex-wrap gap-2 mb-2">
      {#each attachedFiles as file, i}
        <div class="flex items-center gap-1.5 bg-[var(--bg-base)] border border-[var(--border-color)] px-2.5 py-1 rounded-md text-xs">
          <span>{file.type.startsWith('image/') ? '🖼️' : '📄'}</span>
          <span class="truncate max-w-[200px]">{file.name}</span>
          <button on:click={() => (attachedFiles = attachedFiles.filter((_, idx) => idx !== i))} class="hover:text-rose-400">✕</button>
        </div>
      {/each}
    </div>
  {/if}

  <div class="flex items-center gap-2">
    <label class="p-2.5 bg-[var(--bg-base)] hover:opacity-80 border border-[var(--border-color)] rounded-xl cursor-pointer transition" title="Attach Media">
      📎 <input type="file" accept="image/*,application/pdf" multiple on:change={handleFileUpload} class="hidden" />
    </label>

    <button on:click={toggleRecording} class={`p-2.5 rounded-xl border transition ${isRecording ? 'bg-rose-600 animate-pulse text-white' : 'bg-[var(--bg-base)] border-[var(--border-color)]'}`} title="Push-to-Talk">
      🎤
    </button>

    <input
      type="text"
      bind:value={promptText}
      on:keydown={(e) => e.key === 'Enter' && submit()}
      placeholder={isStreaming ? 'Generating... click Stop to cancel' : 'Type your message, describe an image, or speak...'}
      class="flex-1 bg-[var(--input-bg)] text-[var(--text-main)] rounded-xl px-4 py-2.5 text-sm border border-[var(--border-color)] focus:outline-none focus:border-[var(--accent)]"
    />

    {#if isStreaming}
      <button
        on:click={submit}
        class="px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-sm font-bold transition flex items-center gap-1.5 shadow"
      >
        ⏹ Stop
      </button>
    {:else}
      <button
        on:click={submit}
        disabled={!promptText.trim() && attachedFiles.length === 0}
        style="background-color: var(--accent); color: var(--accent-text);"
        class="px-5 py-2.5 disabled:opacity-40 rounded-xl text-sm font-bold transition shadow-sm"
      >
        Send
      </button>
    {/if}
  </div>
</div>
