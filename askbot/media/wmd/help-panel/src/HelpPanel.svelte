<script>
    import { isPanelOpen } from './panel.js';
    import { activeTab } from './settings.js';
    import { slide } from 'svelte/transition';

    import TabBar from './components/TabBar.svelte';
    import LinksHelp from './tabs/LinksHelp.svelte';
    import ImagesHelp from './tabs/ImagesHelp.svelte';
    import StylingHelp from './tabs/StylingHelp.svelte';
    import ListsHelp from './tabs/ListsHelp.svelte';
    import BlockquotesHelp from './tabs/BlockquotesHelp.svelte';
    import CodeHelp from './tabs/CodeHelp.svelte';
    import HtmlHelp from './tabs/HtmlHelp.svelte';
    import TablesHelp from './tabs/TablesHelp.svelte';
    import VideoHelp from './tabs/VideoHelp.svelte';
    import MathHelp from './tabs/MathHelp.svelte';

    $: isOpen = $isPanelOpen;

    // Map tab IDs to components
    const tabComponents = {
        links: LinksHelp,
        images: ImagesHelp,
        styling: StylingHelp,
        lists: ListsHelp,
        blockquotes: BlockquotesHelp,
        code: CodeHelp,
        html: HtmlHelp,
        tables: TablesHelp,
        video: VideoHelp,
        math: MathHelp
    };

    $: currentComponent = tabComponents[$activeTab] || LinksHelp;
</script>

{#if isOpen}
    <div class="help-panel" transition:slide={{ duration: 150 }}>
        <TabBar />
        <div class="help-panel-content" role="tabpanel">
            <svelte:component this={currentComponent} />
        </div>
    </div>
{/if}

<style>
    .help-panel {
        background: var(--info-box-bg);
        border: var(--info-box-border);
        border-bottom: 0;
        border-radius: var(--input-border-radius) var(--input-border-radius) 0 0;
        box-shadow: var(--info-box-box-shadow);
        margin: 0;
        overflow: hidden;
        width: 100%;
    }

    .help-panel-content {
        padding: var(--info-box-padding);
        color: var(--info-box-color);
        font-size: var(--info-box-font-size);
        overflow: hidden;
    }
</style>
