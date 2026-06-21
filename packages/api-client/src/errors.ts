/**
 * FE-6: the client distinguishes 412 (stale lock) from 409 (bad from-state)
 * — never collapsed into one generic error. Real Error subclasses so call
 * sites can `instanceof`-check and React Query onError handlers can branch.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** 412 — the resource changed since the lockVersion this request was built
 * against. The caller must invalidate, refetch, re-present, and let the user
 * retry — never silently retry. */
export class StaleLockError extends ApiError {
  constructor(body: unknown) {
    super(412, body, "The resource has changed since it was loaded (stale lock).");
    this.name = "StaleLockError";
  }
}

/** 409 — the action is no longer valid from the resource's current state
 * (the state moved on). The action is void; never collapsed with 412. */
export class BadFromStateError extends ApiError {
  constructor(body: unknown) {
    super(409, body, "This action is no longer valid for the resource's current state.");
    this.name = "BadFromStateError";
  }
}

export class ValidationError extends ApiError {
  constructor(body: unknown) {
    super(422, body, "The request failed validation.");
    this.name = "ValidationError";
  }
}

export class NotFoundError extends ApiError {
  constructor(body: unknown) {
    super(404, body, "The requested resource was not found.");
    this.name = "NotFoundError";
  }
}

export function errorFromResponse(status: number, body: unknown): ApiError {
  switch (status) {
    case 412:
      return new StaleLockError(body);
    case 409:
      return new BadFromStateError(body);
    case 422:
      return new ValidationError(body);
    case 404:
      return new NotFoundError(body);
    default:
      return new ApiError(status, body);
  }
}
