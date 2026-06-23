import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.test.ts'],
  },
  build: {
    target: "es2022",
    outDir: resolve(__dirname, "dist"),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      formats: ["es"],
      fileName: () => "salah-times-card.js",
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
    minify: "esbuild",
    sourcemap: false,
    cssCodeSplit: false,
    assetsInlineLimit: 100000,
  },
  esbuild: {
    legalComments: "none",
  },
});
