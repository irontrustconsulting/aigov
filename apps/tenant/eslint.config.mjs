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
      // FE-1 package boundary: the tenant app never reaches into the operator
      // app's directory — auth/cookie/pool config is never shared (INV-1).
      // Workspace dependency resolution already makes this physically
      // unreachable via a clean import; this catches a relative-path
      // reach-around.
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/apps/operator/**", "../../operator/**", "../operator/**"],
              message: "apps/tenant must never import from apps/operator (INV-1 plane separation).",
            },
          ],
        },
      ],
    },
  }
);
