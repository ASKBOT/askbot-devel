<script>
    export let id;
    export let label;
    export let active = false;

    import { createEventDispatcher } from 'svelte';
    const dispatch = createEventDispatcher();

    function handleClick() {
        dispatch('select', { id });
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            dispatch('select', { id });
        }
    }
</script>

<button
    type="button"
    class="tab-button"
    class:active
    role="tab"
    aria-selected={active}
    tabindex={active ? 0 : -1}
    on:click={handleClick}
    on:keydown={handleKeydown}
>
    {label}
</button>

<style>
    .tab-button {
        color: var(--action-link-color);
        cursor: pointer;
        transition: color var(--transition-params);
        font-size: var(--small-font-size);
        font-family: inherit;
        padding: 0.25rem 0.5rem;
        border: none;
        background: transparent;
        border-bottom: 2px solid transparent;
        margin-bottom: -1px;
    }

    .tab-button:hover {
        color: var(--action-link-hover-color);
    }

    .tab-button.active {
        color: var(--link-color);
        border-bottom-color: var(--link-color);
    }

    .tab-button:focus {
        outline: none;
    }

    .tab-button:focus-visible {
        outline: 2px solid var(--link-color);
        outline-offset: 2px;
    }
</style>
