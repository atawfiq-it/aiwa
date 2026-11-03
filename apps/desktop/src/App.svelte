<script lang="ts">
  import { onMount } from 'svelte';

  const API_BASE = 'http://127.0.0.1:8000/api/v1';
  let token = '';
  let connectionStatus = 'Connecting...';
  let conversations: any[] = [];
  let currentConversationId: string | null = null;
  let messages: { role: string; content: string }[] = [];
  let promptText = '';
  let isStreaming = false;
  let supervisorStatus: any = null;

  async function loadInitialData() {
    try {
      const healthRes = await fetch('http://127.0.0.1:8000/api/v1/health');
      if (healthRes.ok) {
        connectionStatus = 'Backend Connected';
      }
    } catch {
      connectionStatus = 'Backend Offline';
    }
  }

  async function sendMessage() {
    if (!promptText.trim() || isStreaming) return;

    const userMessage = { role: 'user', content: promptText };
    messages = [...messages, userMessage];
    promptText = '';
    isStreaming = true;

    // Placeholder for streamed assistant response
    const assistantIndex = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];

    try {
      const response = await fetch(`${API_BASE}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-AIWA-Token': token,
        },
        body: JSON.stringify({
          conversation_id: currentConversationId,
          messages: messages.slice(0, -1),
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            try {
              const data = JSON.parse(dataStr);
              if (data.text) {
                messages[assistantIndex].content += data.text;
                messages = [...messages]; // trigger reactivity
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      messages[assistantIndex].content += '\n[Inference Error]';
      messages = [...messages];
    } finally {
      isStreaming = false;
    }
  }

  onMount(() => {
    loadInitialData();
  });
</script>

<div class="flex h-screen bg-slate-900 text-slate-100 font-sans">
  <!-- Sidebar -->
  <aside class="w-64 border-r border-slate-800 p-4 flex flex-col justify-between">
    <div>
      <h1 class="text-xl font-bold tracking-tight text-indigo-400">AIWA Workstation</h1>
      <div class="mt-2 text-xs flex items-center gap-2">
        <span class={`h-2 w-2 rounded-full ${connectionStatus === 'Backend Connected' ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
        <span class="text-slate-400">{connectionStatus}</span>
      </div>

      <div class="mt-6">
        <button class="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-medium transition">
          + New Chat
        </button>
      </div>
    </div>

    <!-- Token entry for dev mode -->
    <div class="border-t border-slate-800 pt-3">
      <label for="token-input" class="text-xs text-slate-400">Session Token</label>
      <input
        id="token-input"
        type="password"
        bind:value={token}
        placeholder="Paste token..."
        class="w-full mt-1 bg-slate-800 text-xs px-2 py-1.5 rounded border border-slate-700 focus:outline-none focus:border-indigo-500"
      />
    </div>
  </aside>

  <!-- Main Chat Workspace -->
  <main class="flex-1 flex flex-col justify-between">
    <!-- Message History -->
    <div class="flex-1 overflow-y-auto p-6 space-y-4">
      {#if messages.length === 0}
        <div class="h-full flex flex-col items-center justify-center text-slate-500">
          <p class="text-lg">No active conversation.</p>
          <p class="text-sm">Start typing below to prompt the local model.</p>
        </div>
      {:else}
        {#each messages as msg}
          <div class={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div class={`max-w-2xl px-4 py-3 rounded-lg text-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'}`}>
              <p class="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <!-- Input Bar -->
    <div class="p-4 border-t border-slate-800 bg-slate-900/50">
      <form on:submit|preventDefault={sendMessage} class="flex gap-2">
        <input
          type="text"
          bind:value={promptText}
          placeholder="Ask anything or analyze context..."
          disabled={isStreaming}
          class="flex-1 bg-slate-800 text-slate-100 rounded-lg px-4 py-2 text-sm border border-slate-700 focus:outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={isStreaming || !promptText.trim()}
          class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg text-sm font-semibold transition"
        >
          Send
        </button>
      </form>
    </div>
  </main>
</div>
