import { defineConfig } from 'vitest/config';

export default defineConfig({
	test: {
		// The first render in a spec file compiles the whole page; under a loaded parallel run that can pass 5 s.
		testTimeout: 20_000,
	},
});
