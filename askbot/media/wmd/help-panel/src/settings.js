import { writable, derived } from 'svelte/store';

// Get askbot settings from global namespace
function getAskbotSettings() {
    const settings = (typeof askbot !== 'undefined' && askbot.settings) || {};
    const data = (typeof askbot !== 'undefined' && askbot.data) || {};
    return {
        mathjaxEnabled: settings.mathjaxEnabled || false,
        videoEmbeddingEnabled: settings.videoEmbeddingEnabled || false,
        autoLinkEnabled: settings.autoLinkEnabled || false,
        userCanUploadImage: data.userCanUploadImage || false
    };
}

// Store for help panel settings
export const settings = writable(getAskbotSettings());

// Tab definitions with conditional visibility
const TAB_DEFINITIONS = [
    { id: 'links', label: gettext('Links'), always: true },
    { id: 'images', label: gettext('Images'), condition: 'userCanUploadImage' },
    { id: 'styling', label: gettext('Styling'), always: true },
    { id: 'lists', label: gettext('Lists'), always: true },
    { id: 'blockquotes', label: gettext('Quotes'), always: true },
    { id: 'code', label: gettext('Code'), always: true },
    { id: 'html', label: gettext('HTML'), always: true },
    { id: 'tables', label: gettext('Tables'), always: true },
    { id: 'video', label: gettext('Video'), condition: 'videoEmbeddingEnabled' },
    { id: 'math', label: gettext('Math'), condition: 'mathjaxEnabled' },
    { id: 'autolink', label: gettext('Auto-link'), condition: 'autoLinkEnabled' }
];

// Derived store for visible tabs based on settings
export const visibleTabs = derived(settings, ($settings) => {
    return TAB_DEFINITIONS.filter(tab => {
        if (tab.always) return true;
        if (tab.condition && $settings[tab.condition]) return true;
        return false;
    });
});

// Active tab store
export const activeTab = writable('links');

// Helper to update settings (called from parent component)
export function updateSettings() {
    settings.set(getAskbotSettings());
}
