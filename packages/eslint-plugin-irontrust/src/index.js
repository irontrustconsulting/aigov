import noLiteralTokenValue from "./rules/no-literal-token-value.js";
import noRawLiveStateQuery from "./rules/no-raw-live-state-query.js";

export default {
  meta: {
    name: "@irontrust/eslint-plugin-irontrust",
  },
  rules: {
    "no-literal-token-value": noLiteralTokenValue,
    "no-raw-live-state-query": noRawLiveStateQuery,
  },
};
