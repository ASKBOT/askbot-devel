import EditorHelpPanel from './EditorHelpPanel.svelte';
import { mount, unmount } from 'svelte';

export function create(options) {
    return mount(EditorHelpPanel, options);
}

export function destroy(instance) {
    unmount(instance);
}
