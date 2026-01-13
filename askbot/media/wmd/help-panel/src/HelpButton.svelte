<script>
    import { isPanelOpen, togglePanel } from './panel.js';

    // Get the open state from the store
    $: isOpen = $isPanelOpen;

    function handleClick() {
        togglePanel();
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            togglePanel();
        }
    }
</script>

<li
    class="wmd-button wmd-help-button"
    class:active={isOpen}
    role="button"
    tabindex="0"
    title="Formatting help"
    aria-label="Toggle formatting help"
    aria-expanded={isOpen}
    on:click={handleClick}
    on:keydown={handleKeydown}
>
</li>

<style>
    .wmd-help-button {
        margin-left: auto;
    }

    .wmd-help-button.active::before {
        color: var(--wmd-button-hover-color);
        background: var(--wmd-button-hover-bg);
    }
</style>
