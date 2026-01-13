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
    import AutoLinkHelp from './tabs/AutoLinkHelp.svelte';

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
        math: MathHelp,
        autolink: AutoLinkHelp
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
        border-radius: var(--info-box-border-radius);
        box-shadow: var(--info-box-box-shadow);
        margin: 0 0 0.5rem;
        overflow: hidden;
    }

    .help-panel-content {
        padding: var(--info-box-padding);
        color: var(--info-box-color);
        font-size: var(--info-box-font-size);
    }
</style>
