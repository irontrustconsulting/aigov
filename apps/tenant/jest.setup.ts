import "@testing-library/jest-dom";

// next/navigation is unavailable in jsdom — provide sensible no-op defaults.
// Tests that need to control useSearchParams values can override per-describe with
// jest.mock("next/navigation", ...) or (useSearchParams as jest.Mock).mockReturnValue(...).
jest.mock("next/navigation", () => ({
  useSearchParams: jest.fn(() => new URLSearchParams()),
  useRouter: jest.fn(() => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() })),
  usePathname: jest.fn(() => "/"),
}));
