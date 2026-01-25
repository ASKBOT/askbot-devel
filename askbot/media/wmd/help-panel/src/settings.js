import { writable, derived } from 'svelte/store';

// Get askbot settings from global namespace
function getAskbotSettings() {
    const settings = (typeof askbot !== 'undefined' && askbot.settings) || {};
    const data = (typeof askbot !== 'undefined' && askbot.data) || {};
    const allowedHtmlElements = settings.allowedHtmlElements || [];
    return {
        mathjaxEnabled: settings.mathjaxEnabled || false,
        videoEmbeddingEnabled: settings.videoEmbeddingEnabled || false,
        autoLinkEnabled: settings.autoLinkEnabled || false,
        autoLinkPatterns: settings.autoLinkPatterns || '',
        autoLinkUrls: settings.autoLinkUrls || '',
        codeFriendlyEnabled: settings.markupCodeFriendly || false,
        userCanUploadImage: data.userCanUploadImage || false,
        allowedHtmlElements: allowedHtmlElements,
        hasAllowedHtmlElements: allowedHtmlElements.length > 0
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
    { id: 'html', label: gettext('HTML'), condition: 'hasAllowedHtmlElements' },
    { id: 'tables', label: gettext('Tables'), always: true },
    { id: 'video', label: gettext('Video'), condition: 'videoEmbeddingEnabled' },
    { id: 'math', label: gettext('Math'), condition: 'mathjaxEnabled' }
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

// Generate user-friendly example from regex pattern
// Supports colon-based patterns: gh:(\d+) -> gh:123, linear:([A-Z]+-\d+) -> linear:DEVS-48
// Returns { text: "gh:123", value: "123" } for URL substitution
function generateExample(pattern) {
    // Match prefix (word chars, colons, hashes) followed by capture group
    // Pattern: gh:(\d+) -> prefix="gh:", captureGroup="\d+"
    // Pattern: linear:([A-Z]+-\d+) -> prefix="linear:", captureGroup="[A-Z]+-\d+"
    const match = pattern.match(/^([a-zA-Z0-9_#@:]+)\(([^)]+)\)/);
    if (match) {
        const prefix = match[1];
        const captureGroup = match[2];

        // Generate example value based on capture group pattern
        let exampleValue;
        if (captureGroup.includes('[A-Z]+-\\d+') || captureGroup.includes('[A-Z]+-[0-9]')) {
            exampleValue = 'DEVS-48';
        } else if (captureGroup.includes('\\d+') || captureGroup.includes('[0-9]')) {
            exampleValue = '123';
        } else if (captureGroup.includes('\\w+')) {
            exampleValue = 'example';
        } else {
            exampleValue = '...';
        }
        return { text: `${prefix}${exampleValue}`, value: exampleValue };
    }

    // Fallback: simplify regex for display
    return { text: pattern.replace(/\([^)]+\)/g, '...'), value: '...' };
}

// Derived store for parsed autolink patterns
export const parsedAutoLinks = derived(settings, ($settings) => {
    if (!$settings.autoLinkEnabled) return [];

    const patterns = ($settings.autoLinkPatterns || '').trim();
    const urls = ($settings.autoLinkUrls || '').trim();
    if (!patterns || !urls) return [];

    const patternLines = patterns.split('\n').filter(Boolean);
    const urlLines = urls.split('\n').filter(Boolean);

    // Must have equal counts for valid configuration
    if (patternLines.length !== urlLines.length) return [];

    return patternLines.map((pattern, idx) => {
        const { text: example, value: exampleValue } = generateExample(pattern);
        const url = urlLines[idx];
        const exampleUrl = url.replace(/\\1/g, exampleValue);
        return { pattern, url, example, exampleUrl };
    });
});
