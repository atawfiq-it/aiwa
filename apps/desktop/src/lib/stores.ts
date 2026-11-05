import { writable } from 'svelte/store';
import type { Character, Conversation, ModelConfig } from './types';

export const API_BASE = 'http://127.0.0.1:8000/api/v1';

export const currentTab = writable<'chat' | 'hf' | 'media' | 'tasks' | 'settings'>('chat');
export const sessionToken = writable<string>('');
export const connectionStatus = writable<string>('Connecting...');

// Chat & Models State
export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const registeredModels = writable<ModelConfig[]>([]);
export const activeModelId = writable<string>('');
export const characters = writable<Character[]>([]);
export const activeCharacterId = writable<string>('');
export const imageGenMode = writable<'none' | 'probable' | 'definitely'>('none');
