import DownvoteCommentPrompt from './DownvoteCommentPrompt.svelte';
import { mount, unmount } from 'svelte';

export function create(options) {
    return mount(DownvoteCommentPrompt, options);
}

export function destroy(instance) {
    unmount(instance);
}
