declare module "jest-axe" {
  export function axe(html: Element | string, options?: unknown): Promise<unknown>;
  export const toHaveNoViolations: {
    toHaveNoViolations(received: unknown): { pass: boolean; message(): string };
  };
}

declare namespace jest {
  interface Matchers<R> {
    toHaveNoViolations(): R;
  }
}
