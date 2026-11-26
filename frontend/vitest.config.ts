import { defineConfig } from 'vitest/config';

// Every machine tests in UTC, like CI: code that shows the device's time while saying "WIB" must fail locally too.
process.env['TZ'] = 'UTC';

export default defineConfig({
	test: {
		// The first render in a spec file compiles the whole page; under a loaded parallel run that can pass 5 s.
		testTimeout: 20_000,
	},
});
