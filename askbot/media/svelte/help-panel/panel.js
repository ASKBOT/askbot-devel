import { writable } from 'svelte/store';

// Store for the panel's open/closed state
export const isPanelOpen = writable(false);

// Toggle the panel
export function togglePanel() {
    isPanelOpen.update(value => !value);
}

// Close the panel
export function closePanel() {
    isPanelOpen.set(false);
}

// Open the panel
export function openPanel() {
    isPanelOpen.set(true);
}
