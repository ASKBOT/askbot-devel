import svelte from 'rollup-plugin-svelte';
import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';
import terser from '@rollup/plugin-terser';

export default {
	input: './EditorHelpPanel.svelte',
	output: {
		format: 'iife',
		name: 'EditorHelpPanel',
		file: '../editor_help_panel.js'
	},
	plugins: [
		svelte({
			emitCss: false
		}),
		resolve({
			browser: true,
			dedupe: importee => importee === 'svelte' || importee.startsWith('svelte/')
		}),
		commonjs(),
		terser()
	]
};
