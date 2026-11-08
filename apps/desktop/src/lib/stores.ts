import { writable } from 'svelte/store';
import type { Character, Conversation, ModelConfig } from './types';

export const API_BASE = 'http://127.0.0.1:8000/api/v1';

// All 7 Navigation Tabs
export const currentTab = writable<'chat' | 'characters' | 'knowledge' | 'media' | 'tasks' | 'hf' | 'settings'>('chat');
export const sessionToken = writable<string>('');
export const connectionStatus = writable<string>('Connecting...');

// Models & Hardware
export const registeredModels = writable<ModelConfig[]>([]);
export const activeModelId = writable<string>('');
export const supervisorStatus = writable<any>(null);

// Characters & Chat State
export const conversations = writable<Conversation[]>([]);
export const activeConversationId = writable<string | null>(null);
export const characters = writable<Character[]>([]);
export const activeCharacterId = writable<string>('');
export const imageGenMode = writable<'none' | 'probable' | 'definitely'>('none');
