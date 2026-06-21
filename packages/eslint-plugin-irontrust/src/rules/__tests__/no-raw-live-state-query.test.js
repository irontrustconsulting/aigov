import { test } from "node:test";
import assert from "node:assert/strict";
import { Linter } from "eslint";
import rule from "../no-raw-live-state-query.js";

const linter = new Linter();
const config = {
  languageOptions: { ecmaVersion: 2022, sourceType: "module" },
  plugins: { irontrust: { rules: { "no-raw-live-state-query": rule } } },
  rules: { "irontrust/no-raw-live-state-query": "error" },
};

test("a raw useQuery against a live-state key fails", () => {
  const messages = linter.verify(
    'useQuery({ queryKey: ["lifecycle-state", id], queryFn: fetchIt });',
    config
  );
  assert.equal(messages.length, 1);
  assert.match(messages[0].message, /lifecycle-state/);
});

test("a raw useQuery against a non-live-state key passes", () => {
  const messages = linter.verify(
    'useQuery({ queryKey: ["systems-list"], queryFn: fetchIt });',
    config
  );
  assert.equal(messages.length, 0);
});

test("useLiveState itself is not flagged (different callee name)", () => {
  const messages = linter.verify(
    'useLiveState(["lifecycle-state", id], fetchIt);',
    config
  );
  assert.equal(messages.length, 0);
});
