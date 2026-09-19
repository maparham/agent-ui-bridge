import { defineConfig } from "vitest/config";

// .test.ts files are pure logic and run in the fast `node` environment; the
// DOM-touching ones (tab.test.ts, tabBridge.test.ts) declare
// `// @vitest-environment jsdom` on their first line.
export default defineConfig({
  test: {
    include: ["src/**/*.{test.ts,test.tsx}"],
    environment: "node",
  },
});
