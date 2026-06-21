import { test } from "node:test";
import assert from "node:assert/strict";
import { Linter } from "eslint";
import rule from "../no-literal-token-value.js";

const linter = new Linter();
const config = {
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
  plugins: { irontrust: { rules: { "no-literal-token-value": rule } } },
  rules: { "irontrust/no-literal-token-value": "error" },
};

test("a hex colour in className is flagged", () => {
  const messages = linter.verify('const x = <div className="bg-[#fff]" />;', config);
  assert.equal(messages.length, 1);
});

test("a Tailwind arbitrary-value bracket is flagged", () => {
  const messages = linter.verify('const x = <div className="p-[13px]" />;', config);
  assert.equal(messages.length, 1);
});

test("a token-based className passes", () => {
  const messages = linter.verify('const x = <div className="bg-accent p-4" />;', config);
  assert.equal(messages.length, 0);
});

test("a literal inline style is flagged", () => {
  const messages = linter.verify('const x = <div style={{ color: "#fff" }} />;', config);
  assert.equal(messages.length, 1);
});
