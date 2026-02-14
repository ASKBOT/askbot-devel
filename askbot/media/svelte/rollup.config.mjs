import svelte from 'rollup-plugin-svelte';
import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import terser from '@rollup/plugin-terser';
import { existsSync } from 'fs';

const sharedPlugins = () => [
	svelte({ emitCss: false }),
	resolve({
		browser: true,
		dedupe: importee => importee === 'svelte' || importee.startsWith('svelte/')
	}),
	commonjs(),
	terser()
];

const components = {
	'help-panel': {
		input: './help-panel/EditorHelpPanel.svelte',
		output: {
			format: 'iife',
			name: 'EditorHelpPanel',
			file: './dist/editor_help_panel.js'
		},
		plugins: sharedPlugins()
	},
	'downvote-comment': {
		input: './downvote-comment/DownvoteCommentPrompt.svelte',
		output: {
			format: 'iife',
			name: 'DownvoteCommentPrompt',
			file: './dist/downvote_comment_prompt.js'
		},
		plugins: sharedPlugins()
	}
};

// Support --configComponent flag to build a single component
const args = process.argv;
const configIdx = args.indexOf('--configComponent');
let selected;
if (configIdx !== -1 && args[configIdx + 1]) {
	const target = args[configIdx + 1];
	if (!components[target]) {
		const available = Object.keys(components).join(', ');
		throw new Error(`Unknown component: ${target}. Available: ${available}`);
	}
	selected = components[target];
} else {
	// Build only components whose input exists
	selected = Object.values(components).filter(c => existsSync(c.input));
}

export default selected;
