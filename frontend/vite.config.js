import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // Lets the frontend call "/api/..." and have it forwarded to Flask
      "/api": "http://localhost:5000",
    },
  },
});
