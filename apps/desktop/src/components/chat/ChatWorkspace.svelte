<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../../lib/api';
  import {
    activeCharacterId,
    activeConversationId,
    conversations,
  } from '../../lib/stores';
  import ChatHeader from './ChatHeader.svelte';
  import ChatSidebar from './ChatSidebar.svelte';
  import InputBar from './InputBar.svelte';
  import MessageList from './MessageList.svelte';
  import PersonaPanel from './PersonaPanel.svelte';

  let messages: {
    role: string;
    content: string;
    image_paths?: string[];
    is_truncated?: boolean;
  }[] = [];
  let isStreaming = false;
  let isPersonaPanelOpen = true;
  let currentAbortController: AbortController | null = null;

  async function loadConversation(id: string) {
    $activeConversationId = id;
    const res = await apiFetch(`/conversations/${id}`);
    if (res.ok) {
      const data = await res.json();
      messages = data.messages.map((m: any) => ({
        role: m.role,
        content: m.content,
      }));
    }
  }

  function stopGeneration() {
    if (currentAbortController) {
      currentAbortController.abort();
      currentAbortController = null;
      isStreaming = false;
    }
  }

  function populateQuickPrompt(promptTextTemplate: string) {
    const inputElement = document.querySelector('input[type="text"]') as HTMLInputElement;
    if (inputElement) {
      inputElement.value = promptTextTemplate + ' ';
      inputElement.focus();
      inputElement.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  function continueLastMessage() {
    if (messages.length === 0 || isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role === 'assistant') {
      lastMsg.is_truncated = false;
      handleSend('Please continue writing from exactly where you left off, without repeating yourself.', []);
    }
  }

  async function handleSend(text: string, images: string[]) {
    if (!$activeConversationId) {
      const convRes = await apiFetch('/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: text.slice(0, 30) }),
      });
      if (convRes.ok) {
        const c = await convRes.json();
        $conversations = [c, ...$conversations];
        $activeConversationId = c.id;
      }
    }

    // Persist user prompt to SQLite
    await apiFetch(`/conversations/${$activeConversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: 'user', content: text }),
    });

    apiFetch('/conversations').then(async (res) => {
      if (res.ok) $conversations = await res.json();
    });

    messages = [...messages, { role: 'user', content: text, image_paths: images }];
    isStreaming = true;
    currentAbortController = new AbortController();

    const assistantIdx = messages.length;
    messages = [...messages, { role: 'assistant', content: '' }];

    try {
      const response = await apiFetch('/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: currentAbortController.signal,
        body: JSON.stringify({
          conversation_id: $activeConversationId,
          character_id: $activeCharacterId || null,
          messages: messages.slice(0, -1),
        }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        for (const line of decoder.decode(value).split('\n')) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6).trim());
              if (data.text) {
                messages[assistantIdx].content += data.text;
                messages = [...messages];
              }
              if (data.finish_reason === 'length') {
                messages[assistantIdx].is_truncated = true;
                messages = [...messages];
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        messages[assistantIdx].content += ' [Generation stopped]';
      } else {
        messages[assistantIdx].content += `\n[Error: ${e.message}]`;
      }
      messages = [...messages];
    } finally {
      isStreaming = false;
      currentAbortController = null;
    }
  }

  onMount(() => {
    if ($conversations.length > 0 && !$activeConversationId) {
      loadConversation($conversations[0].id);
    }
  });
</script>

<div class="flex-1 flex overflow-hidden relative">
  <ChatSidebar onSelectConversation={loadConversation} />

  <div class="flex-1 flex flex-col bg-[var(--bg-base)]">
    <!-- Pass isPersonaPanelOpen to header -->
    <ChatHeader bind:isPersonaPanelOpen />

    <MessageList
      {messages}
      onSelectQuickPrompt={populateQuickPrompt}
      onContinueMessage={continueLastMessage}
    />

    <InputBar
      {isStreaming}
      onSendMessage={handleSend}
      onStopGeneration={stopGeneration}
    />
  </div>

  <!-- Re-open pill on right edge when panel is collapsed -->
  {#if !isPersonaPanelOpen}
    <button
      type="button"
      on:click={() => (isPersonaPanelOpen = true)}
      class="absolute right-0 top-1/2 -translate-y-1/2 bg-[var(--bg-card)] border-l border-y border-[var(--border-color)] px-1.5 py-4 rounded-l-xl text-xs text-[var(--text-muted)] hover:text-indigo-400 hover:bg-[var(--bg-base)] shadow-lg transition flex flex-col items-center gap-1 z-10"
      title="Open Persona Profile"
    >
      <span>👤</span>
      <span class="text-[9px] font-mono [writing-mode:vertical-lr]">PERSONA</span>
    </button>
  {/if}

  <!-- Persona Presence Drawer -->
  <PersonaPanel {isStreaming} bind:isOpen={isPersonaPanelOpen} />
</div>
