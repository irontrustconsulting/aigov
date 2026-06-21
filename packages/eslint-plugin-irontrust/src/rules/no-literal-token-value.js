/**
 * FE-3: no literal colour/spacing/etc in components — only design tokens
 * (packages/tokens) via the Tailwind preset. Flags:
 *   - hex colours anywhere in a className/style string or object
 *   - Tailwind arbitrary-value brackets (bg-[#fff], p-[13px], text-[14px])
 *     in a className string — any bracketed utility value bypasses the
 *     token layer, not just colours, so the check is broad on purpose.
 */

const HEX_COLOUR = /#[0-9a-fA-F]{3,8}\b/;
const ARBITRARY_VALUE = /-\[[^\]]+\]/;

function checkStringLiteral(node, context) {
  const value = node.value;
  if (typeof value !== "string") return;
  if (HEX_COLOUR.test(value) || ARBITRARY_VALUE.test(value)) {
    context.report({
      node,
      message:
        "No literal colour/spacing values or Tailwind arbitrary-value brackets — use a token from @irontrust/tokens via the Tailwind preset.",
    });
  }
}

export default {
  meta: {
    type: "problem",
    docs: {
      description: "Disallow literal colour/spacing values bypassing the token layer (FE-3).",
    },
    schema: [],
  },
  create(context) {
    return {
      JSXAttribute(node) {
        if (node.name.type !== "JSXIdentifier") return;
        if (node.name.name === "className" && node.value?.type === "Literal") {
          checkStringLiteral(node.value, context);
        }
        if (node.name.name === "style" && node.value?.type === "JSXExpressionContainer") {
          const expr = node.value.expression;
          if (expr.type === "ObjectExpression") {
            for (const prop of expr.properties) {
              if (prop.type === "Property" && prop.value.type === "Literal") {
                checkStringLiteral(prop.value, context);
                if (typeof prop.value.value === "number") {
                  context.report({
                    node: prop,
                    message:
                      "No literal numeric style values — use a token from @irontrust/tokens via the Tailwind preset.",
                  });
                }
              }
            }
          }
        }
      },
    };
  },
};
