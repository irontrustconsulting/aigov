import tseslint from "typescript-eslint";
import irontrust from "@irontrust/eslint-plugin-irontrust";

export default tseslint.config(
  {
    ignores: ["node_modules/**", "dist/**"],
  },
  ...tseslint.configs.recommended,
  {
    plugins: {
      "@irontrust": irontrust,
    },
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@irontrust/no-literal-token-value": "error",
      "@irontrust/no-raw-live-state-query": "error",
    },
  }
);
