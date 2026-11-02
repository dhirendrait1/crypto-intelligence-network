/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_CIN_API_BASE_URL?: string;
  readonly VITE_CIN_MARKETS_ENABLED?: string;
  readonly VITE_CIN_COINBASE_RESEARCH_UI_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
