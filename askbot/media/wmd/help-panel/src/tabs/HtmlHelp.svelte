<script>
    import { settings } from '../settings.js';

    // Define tag categories with their display names
    const TAG_CATEGORIES = [
        {
            id: 'formatting',
            labelKey: 'Formatting tags',
            tags: ['b', 'i', 'em', 'strong', 'code', 'pre', 'blockquote', 'br', 'hr',
                   'u', 's', 'strike', 'del', 'ins', 'sub', 'sup', 'small', 'big',
                   'kbd', 'samp', 'tt', 'var', 'cite', 'dfn', 'abbr', 'acronym',
                   'q', 'address', 'center']
        },
        {
            id: 'structure',
            labelKey: 'Structure tags',
            tags: ['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                   'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'dir']
        },
        {
            id: 'tables',
            labelKey: 'Tables',
            tags: ['table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
                   'caption', 'col', 'colgroup']
        },
        {
            id: 'media',
            labelKey: 'Media',
            tags: ['a', 'img', 'param']
        }
    ];

    // Filter categories to only show tags that are allowed
    $: allowedSet = new Set($settings.allowedHtmlElements || []);
    $: visibleCategories = TAG_CATEGORIES
        .map(category => ({
            ...category,
            allowedTags: category.tags.filter(tag => allowedSet.has(tag))
        }))
        .filter(category => category.allowedTags.length > 0);
</script>

<div class="help-content">
    <p class="help-intro">{gettext('Some HTML tags are allowed in posts.')}</p>

    {#each visibleCategories as category}
        <div class="help-section">
            <h4>{gettext(category.labelKey)}</h4>
            <p class="help-note">
                {#each category.allowedTags as tag, index}
                    <code>&lt;{tag}&gt;</code>{#if index < category.allowedTags.length - 1}, {/if}
                {/each}
            </p>
        </div>
    {/each}

    <div class="help-section">
        <h4>{gettext('Note')}</h4>
        <p class="help-note">{gettext('Scripts, iframes, and other potentially unsafe tags are filtered out for security.')}</p>
    </div>
</div>
