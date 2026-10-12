import { defineConfig } from "@playwright/test";
import os from "os";
import path from "path";

// E2E работает с отдельной базой, чтобы не смешивать тестовые сделки с рабочими.
const e2eData = path.join(os.tmpdir(), "deal-copilot-e2e");
const python = process.env.E2E_PYTHON || "python";
const mockExtraction = JSON.stringify({
  fields: [{
    key: "area_m2", label: "Площадь", value: "1200", unit: "м²",
    source_fragment: "Общая площадь объекта 1200 м²", confidence: 0.9,
  }],
  missing_fields: [],
  contradictions: [],
});

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    headless: true,
  },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DEMO_MODE: "true",
        LLM_PROVIDER: "mock",
        OLLAMA_MODELS: "",
        DATABASE_URL: `sqlite:///${path.join(e2eData, "e2e.db").split(path.sep).join("/")}`,
        DATA_DIR: e2eData,
        UPLOAD_DIR: path.join(e2eData, "uploads"),
        CORS_ORIGINS: "http://127.0.0.1:3000",
        MOCK_EXTRACTION_PAYLOAD: mockExtraction,
      },
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000/api" },
    },
  ],
});
