<script>
    import { onMount, onDestroy, tick } from 'svelte';
    import TabButton from './TabButton.svelte';
    import OverflowDropdown from './OverflowDropdown.svelte';
    import { visibleTabs, activeTab } from '../settings.js';

    let containerEl;
    let tabButtonEls = [];
    let lastContainerWidth = 0;
    let tabWidths = [];
    let overflowIndex = -1; // Index where overflow starts (-1 = no overflow)
    let pinnedTabId = null; // Tab promoted from dropdown (stays first)

    const DROPDOWN_WIDTH = 40; // Approximate width for "..." button
    const GAP = 2; // Gap between tabs in pixels
    const WIDTH_THRESHOLD = 10; // Minimum width change to trigger recalc

    function handleSelect(event) {
        activeTab.set(event.detail.id);
        // Don't change pinned tab when selecting visible tabs
    }

    function handleDropdownSelect(event) {
        const tabId = event.detail.id;
        activeTab.set(tabId);
        // Pin this tab so it stays first
        pinnedTabId = tabId;
    }

    function measureTabs(force = false) {
        if (!containerEl) return;

        const currentWidth = containerEl.offsetWidth;

        // Skip if width hasn't changed significantly (prevents oscillation)
        if (!force && Math.abs(currentWidth - lastContainerWidth) < WIDTH_THRESHOLD) {
            return;
        }
        lastContainerWidth = currentWidth;

        // Measure each tab button
        tabWidths = tabButtonEls.map(el => el ? el.offsetWidth : 0);

        // Calculate how many tabs fit
        let usedWidth = 0;
        let newOverflowIndex = -1;

        for (let i = 0; i < tabWidths.length; i++) {
            const tabWidth = tabWidths[i] + (i > 0 ? GAP : 0);
            const remainingTabs = tabWidths.length - i - 1;
            const needsDropdown = remainingTabs > 0;
            const availableWidth = currentWidth - (needsDropdown ? DROPDOWN_WIDTH : 0);

            if (usedWidth + tabWidth > availableWidth) {
                // This tab doesn't fit, start overflow here
                // But always show at least 1 tab
                newOverflowIndex = Math.max(1, i);
                break;
            }
            usedWidth += tabWidth;
        }

        // Only update if changed (prevents render loops)
        if (newOverflowIndex !== overflowIndex) {
            overflowIndex = newOverflowIndex;
        }
    }

    let resizeObserver;
    let measureTimeout;

    function debouncedMeasure() {
        if (measureTimeout) clearTimeout(measureTimeout);
        measureTimeout = setTimeout(measureTabs, 50);
    }

    onMount(async () => {
        // Wait for DOM to be fully ready
        await tick();
        // Additional frame to ensure layout is complete
        requestAnimationFrame(() => {
            measureTabs(true);
        });

        // Watch for container resize
        resizeObserver = new ResizeObserver(debouncedMeasure);
        resizeObserver.observe(containerEl);
    });

    onDestroy(() => {
        if (resizeObserver) {
            resizeObserver.disconnect();
        }
        if (measureTimeout) {
            clearTimeout(measureTimeout);
        }
    });

    // Reorder tabs only if a tab was pinned from the dropdown
    $: orderedTabs = (() => {
        if (!pinnedTabId) return $visibleTabs;
        const pinnedIndex = $visibleTabs.findIndex(tab => tab.id === pinnedTabId);
        if (pinnedIndex <= 0) return $visibleTabs; // Already first or not found
        const result = [...$visibleTabs];
        const [pinnedTab] = result.splice(pinnedIndex, 1);
        result.unshift(pinnedTab);
        return result;
    })();

    // Re-measure when pinned tab changes (visibleTabs handled by ResizeObserver)
    $: if (pinnedTabId) {
        tick().then(() => {
            requestAnimationFrame(() => measureTabs(true));
        });
    }

    $: inlineTabs = overflowIndex === -1
        ? orderedTabs
        : orderedTabs.slice(0, overflowIndex);

    $: overflowTabs = overflowIndex === -1
        ? []
        : orderedTabs.slice(overflowIndex);
</script>

<div class="tab-bar" role="tablist" aria-label="Help topics" bind:this={containerEl}>
    {#each inlineTabs as tab, i (tab.id)}
        <span bind:this={tabButtonEls[i]}>
            <TabButton
                id={tab.id}
                label={tab.label}
                active={$activeTab === tab.id}
                on:select={handleSelect}
            />
        </span>
    {/each}
    {#if overflowTabs.length > 0}
        <OverflowDropdown
            tabs={overflowTabs}
            activeTabId={$activeTab}
            on:select={handleDropdownSelect}
        />
    {/if}
</div>

<!-- Hidden tabs for measuring -->
<div class="measure-container" aria-hidden="true">
    {#each orderedTabs as tab, i (tab.id)}
        <span bind:this={tabButtonEls[i]} class="measure-tab">
            <TabButton
                id={tab.id}
                label={tab.label}
                active={false}
            />
        </span>
    {/each}
</div>

<style>
    .tab-bar {
        display: flex;
        flex-wrap: nowrap;
        gap: 0.125rem;
        border-bottom: var(--border-width) var(--border-style) var(--editor-border-color);
        padding: 0;
        margin: 0 0 0.5rem;
    }

    .measure-container {
        position: absolute;
        visibility: hidden;
        height: 0;
        overflow: hidden;
        display: flex;
        gap: 0.125rem;
    }

    .measure-tab {
        white-space: nowrap;
    }
</style>
