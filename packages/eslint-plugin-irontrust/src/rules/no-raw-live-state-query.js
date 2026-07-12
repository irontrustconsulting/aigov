/**
 * FE-7 / INV-25 / INV-32: lifecycle/gate-vector/coverage/authorisation reads
 * are non-cacheable verdicts and MUST go through useLiveState (staleTime: 0,
 * mandatory refetch), never a raw TanStack useQuery call, which would default
 * to a cached staleTime and risk rendering a stale lifecycle/authz verdict as
 * settled across a transition.
 *
 * This list must stay in sync with LIVE_STATE_KEYS in
 * packages/api-client/src/query-keys.ts — it is duplicated here (rather than
 * imported) because ESLint rule modules run outside the TS build graph and
 * importing app source into a lint rule is its own kind of coupling hazard.
 */
const LIVE_STATE_KEYS = new Set([
  "lifecycle-state",
  "gate-vector",
  "control-coverage",
  "deployment-authorisation",
  "portfolio",
  "system-rollup",
  "clearance-queue",
]);

export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow raw useQuery against a live-state query key — use useLiveState instead (FE-7).",
    },
    schema: [],
  },
  create(context) {
    return {
      CallExpression(node) {
        if (node.callee.type !== "Identifier" || node.callee.name !== "useQuery") return;
        const [arg] = node.arguments;
        if (!arg || arg.type !== "ObjectExpression") return;
        const queryKeyProp = arg.properties.find(
          (p) => p.type === "Property" && p.key.type === "Identifier" && p.key.name === "queryKey"
        );
        if (!queryKeyProp || queryKeyProp.value.type !== "ArrayExpression") return;
        const [first] = queryKeyProp.value.elements;
        if (!first || first.type !== "Literal" || typeof first.value !== "string") return;
        if (LIVE_STATE_KEYS.has(first.value)) {
          context.report({
            node,
            message: `"${first.value}" is a live-state query key — use useLiveState from @irontrust/api-client instead of a raw useQuery (FE-7, INV-25, INV-32).`,
          });
        }
      },
    };
  },
};
