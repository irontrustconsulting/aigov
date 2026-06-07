"""
app/cli/admin.py

Platform-operator CLI -- internal tooling, run by staff from a trusted
environment and authenticated simply by possession of the provisioner + AWS
credentials. It is NOT exposed over HTTP; there is no public provisioning
surface to defend.

    python -m app.cli.admin provision \
        --org "Acme Corp" --slug acme \
        --owner-email jane@acme.com --owner-name "Jane Doe" \
        --actor-sub <sub> --actor-email alice@irontrust.io

    python -m app.cli.admin list-tenants
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import typer
from sqlalchemy import select

from app.db.session import ProvisionerSessionLocal
from app.models import Tenant
from app.services.provisioning import AlreadyProvisioned, provision_tenant
from app.services.operator_provisioning import (
    OperatorAlreadyExists,
    OperatorProvisioningError,
    RoleNotFound,
    provision_operator,
)

app = typer.Typer(help="Platform-operator tools (internal use only).")


def _cli_actor(actor_sub: str | None, actor_email: str | None):
    """Build a minimal CurrentOperator-compatible object from CLI flags.

    Returns None for the genesis bootstrap (no prior operator). When provided,
    both sub and email are required — neither is self-asserted; the person
    running the CLI holds the provisioner credentials.
    """
    if actor_sub is None and actor_email is None:
        return None
    if not actor_sub or not actor_email:
        typer.secho(
            "Both --actor-sub and --actor-email are required together.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Minimal duck-typed object; audit helper only reads .cognito_sub and .email
    @dataclass
    class _CLIActor:
        cognito_sub: str
        email: str
        id: uuid.UUID = field(default_factory=uuid.uuid4)
        display_name: str | None = None
        permissions: frozenset = field(default_factory=frozenset)

    return _CLIActor(cognito_sub=actor_sub, email=actor_email)


@app.command()
def provision(
    org: str = typer.Option(..., help="Organisation name"),
    slug: str = typer.Option(..., help="Unique org slug"),
    owner_email: str = typer.Option(..., help="First owner's email address"),
    owner_name: str = typer.Option(..., help="First owner's display name"),
    actor_sub: str | None = typer.Option(None, help="Cognito sub of the acting operator (for audit)"),
    actor_email: str | None = typer.Option(None, help="Email of the acting operator (for audit)"),
) -> None:
    """Stand up a new tenant and invite its first owner (the de-facto admin)."""
    actor = _cli_actor(actor_sub, actor_email)
    try:
        tenant_id, owner_id = provision_tenant(
            org_name=org,
            slug=slug,
            owner_email=owner_email,
            owner_name=owner_name,
            actor=actor,
            source="cli",
        )
    except AlreadyProvisioned as e:
        typer.secho(f"Already provisioned: {e}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    typer.secho("Provisioned.", fg=typer.colors.GREEN)
    typer.echo(f"  tenant_id : {tenant_id}")
    typer.echo(f"  owner_id  : {owner_id}")
    typer.echo(f"  An invite email has been sent to {owner_email}.")


@app.command("create-operator")
def create_operator(
    email: str = typer.Option(..., help="Operator's email address"),
    display_name: str = typer.Option(..., help="Operator's display name"),
    role: str = typer.Option("provisioner", help="Initial role to grant (default: provisioner)"),
    actor_sub: str | None = typer.Option(None, help="Cognito sub of the acting operator (for audit; omit for genesis bootstrap)"),
    actor_email: str | None = typer.Option(None, help="Email of the acting operator (for audit; omit for genesis bootstrap)"),
) -> None:
    """Create a platform operator: Cognito user + operator row + initial role grant."""
    actor = _cli_actor(actor_sub, actor_email)
    try:
        operator_id, sub = provision_operator(
            email=email,
            display_name=display_name,
            role_key=role,
            actor=actor,
            source="cli",
        )
    except OperatorAlreadyExists as e:
        typer.secho(f"Already exists: {e}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)
    except RoleNotFound as e:
        typer.secho(f"Role not found: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except OperatorProvisioningError as e:
        typer.secho(f"Provisioning failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("Operator created.", fg=typer.colors.GREEN)
    typer.echo(f"  operator_id : {operator_id}")
    typer.echo(f"  cognito_sub : {sub}")
    typer.echo(f"  role        : {role}")
    typer.echo(f"  An invite email has been sent to {email}.")


@app.command("list-tenants")
def list_tenants() -> None:
    """List every tenant -- the cross-tenant read we removed from the API.

    Uses the provisioner session: it already holds SELECT on `tenant` plus
    BYPASSRLS, so it's the narrowest credential that can legitimately see
    across tenants -- and it's an operator command, never a tenant-facing one.
    """
    session = ProvisionerSessionLocal()
    try:
        rows = session.scalars(select(Tenant).order_by(Tenant.created_at)).all()
    finally:
        session.close()

    if not rows:
        typer.echo("No tenants.")
        return
    for t in rows:
        typer.echo(f"{t.id}  {t.slug:<20}  {t.name}")


if __name__ == "__main__":
    app()
