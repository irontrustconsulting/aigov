import tseslint from "typescript-eslint";
import irontrust from "@irontrust/eslint-plugin-irontrust";

export default tseslint.config(
  {
    ignores: [".next/**", "node_modules/**", "next-env.d.ts"],
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
      // FE-1 package boundary: the operator app never reaches into the tenant
      // app's directory — auth/cookie/pool config is never shared (INV-1).
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/apps/tenant/**", "../../tenant/**", "../tenant/**"],
              message: "apps/operator must never import from apps/tenant (INV-1 plane separation).",
            },
          ],
        },
      ],
    },
  }
);
