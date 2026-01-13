<script>
    import { onMount, onDestroy } from 'svelte';
    import { isPanelOpen, togglePanel, closePanel } from './panel.js';
    import HelpPanel from './HelpPanel.svelte';

    // Props
    export let buttonRow = null;

    // Local state
    let helpButton = null;

    $: isOpen = $isPanelOpen;

    function handleButtonClick() {
        togglePanel();
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            togglePanel();
        }
    }

    function updateButtonState(open) {
        if (helpButton) {
            helpButton.setAttribute('aria-expanded', open);
            if (open) {
                helpButton.classList.add('active');
            } else {
                helpButton.classList.remove('active');
            }
        }
    }

    // Subscribe to store changes
    const unsubscribe = isPanelOpen.subscribe(value => {
        updateButtonState(value);
    });

    onMount(() => {
        if (buttonRow) {
            // Create the help button element
            helpButton = document.createElement('li');
            helpButton.className = 'wmd-button wmd-help-button';
            helpButton.setAttribute('role', 'button');
            helpButton.setAttribute('tabindex', '0');
            helpButton.setAttribute('title', 'Formatting help');
            helpButton.setAttribute('aria-label', 'Toggle formatting help');
            helpButton.setAttribute('aria-expanded', 'false');

            // Add event listeners
            helpButton.addEventListener('click', handleButtonClick);
            helpButton.addEventListener('keydown', handleKeydown);

            // Append to button row
            buttonRow.appendChild(helpButton);

            // Set initial state
            updateButtonState($isPanelOpen);
        }
    });

    onDestroy(() => {
        unsubscribe();
        if (helpButton) {
            helpButton.removeEventListener('click', handleButtonClick);
            helpButton.removeEventListener('keydown', handleKeydown);
            helpButton.remove();
        }
    });
</script>

<HelpPanel />

<style>
    :global(.wmd-help-button) {
        margin-left: auto !important;
    }

    :global(.wmd-help-button.active::before) {
        color: var(--wmd-button-hover-color) !important;
        background: var(--wmd-button-hover-bg) !important;
    }
</style>
