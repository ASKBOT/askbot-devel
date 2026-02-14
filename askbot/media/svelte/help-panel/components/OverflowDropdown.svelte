<script>
    import { onMount, onDestroy, createEventDispatcher } from 'svelte';

    export let tabs = [];
    export let activeTabId = null;

    const dispatch = createEventDispatcher();

    let isOpen = false;
    let triggerEl;
    let menuEl;
    let focusedIndex = -1;

    $: hasActiveTab = tabs.some(tab => tab.id === activeTabId);

    function toggleDropdown() {
        isOpen = !isOpen;
        if (isOpen) {
            focusedIndex = -1;
        }
    }

    function closeDropdown() {
        isOpen = false;
        focusedIndex = -1;
    }

    function selectTab(tabId) {
        dispatch('select', { id: tabId });
        closeDropdown();
    }

    function handleTriggerKeydown(event) {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            toggleDropdown();
        } else if (event.key === 'Escape') {
            closeDropdown();
        } else if (event.key === 'ArrowDown' && isOpen) {
            event.preventDefault();
            focusedIndex = 0;
        }
    }

    function handleMenuKeydown(event) {
        if (event.key === 'Escape') {
            closeDropdown();
            triggerEl?.focus();
        } else if (event.key === 'ArrowDown') {
            event.preventDefault();
            focusedIndex = Math.min(focusedIndex + 1, tabs.length - 1);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            focusedIndex = Math.max(focusedIndex - 1, 0);
        } else if (event.key === 'Enter' && focusedIndex >= 0) {
            event.preventDefault();
            selectTab(tabs[focusedIndex].id);
        }
    }

    function handleClickOutside(event) {
        if (isOpen && triggerEl && menuEl) {
            if (!triggerEl.contains(event.target) && !menuEl.contains(event.target)) {
                closeDropdown();
            }
        }
    }

    onMount(() => {
        document.addEventListener('click', handleClickOutside);
    });

    onDestroy(() => {
        document.removeEventListener('click', handleClickOutside);
    });

    $: if (isOpen && menuEl && focusedIndex >= 0) {
        const items = menuEl.querySelectorAll('.overflow-item');
        items[focusedIndex]?.focus();
    }
</script>

<div class="overflow-dropdown">
    <button
        bind:this={triggerEl}
        type="button"
        class="overflow-trigger"
        class:has-active={hasActiveTab}
        aria-haspopup="true"
        aria-expanded={isOpen}
        on:click={toggleDropdown}
        on:keydown={handleTriggerKeydown}
    >
        &hellip;
    </button>

    {#if isOpen}
        <ul
            bind:this={menuEl}
            class="overflow-menu"
            role="menu"
            on:keydown={handleMenuKeydown}
        >
            {#each tabs as tab, i (tab.id)}
                <li
                    class="overflow-item"
                    class:active={tab.id === activeTabId}
                    class:focused={i === focusedIndex}
                    role="menuitem"
                    tabindex="-1"
                    on:click={() => selectTab(tab.id)}
                    on:keydown={(e) => e.key === 'Enter' && selectTab(tab.id)}
                >
                    {tab.label}
                </li>
            {/each}
        </ul>
    {/if}
</div>

<style>
    .overflow-dropdown {
        position: relative;
        display: inline-flex;
        align-items: center;
    }

    .overflow-trigger {
        color: var(--action-link-color);
        font-size: var(--small-font-size);
        font-family: inherit;
        padding: 0.25rem 0.5rem;
        border: none;
        background: transparent;
        cursor: pointer;
        transition: color var(--transition-params);
    }

    .overflow-trigger:hover {
        color: var(--action-link-hover-color);
    }

    .overflow-trigger.has-active {
        font-weight: var(--font-weight-bold);
        color: var(--link-color);
    }

    .overflow-trigger:focus {
        outline: none;
    }

    .overflow-trigger:focus-visible {
        outline: 2px solid var(--link-color);
        outline-offset: 2px;
    }

    .overflow-menu {
        position: absolute;
        background: var(--bg-color);
        border: var(--toolbar-dropdown-menu-border);
        border-radius: var(--toolbar-dropdown-menu-border-radius);
        box-shadow: var(--toolbar-dropdown-menu-box-shadow);
        padding: var(--toolbar-dropdown-menu-padding);
        z-index: 10000;
        right: 0;
        top: 100%;
        margin-top: 0.25rem;
        list-style: none;
        min-width: 8rem;
    }

    .overflow-item {
        padding: var(--toolbar-dropdown-menu-item-padding);
        cursor: pointer;
        color: var(--fg-color);
        font-size: var(--small-font-size);
        white-space: nowrap;
    }

    .overflow-item:hover,
    .overflow-item.focused {
        background: var(--toolbar-dropdown-menu-item-hover-bg);
        color: var(--bg-color);
    }

    .overflow-item.active {
        font-weight: var(--font-weight-bold);
    }
</style>
