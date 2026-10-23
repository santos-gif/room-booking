// src/env.d.ts

declare interface Env {
	readonly NODE_ENV: string;
	/** The only NG_APP_* value, and it is public: everything NG_APP_* is inlined into the bundle. */
	readonly NG_APP_API_URL: string;
}

declare interface ImportMeta {
	readonly env: Env;
}

