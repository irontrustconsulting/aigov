"""
app/cli/admin.py

Platform-operator CLI -- internal tooling, run by staff from a trusted
environment and authenticated simply by possession of the provisioner + AWS
credentials. It is NOT exposed over HTTP; there is no public provisioning
surface to defend.

    python -m app.cli.admin provision \
        --org "Acme Corp" --slug acme \
        --owner-email jane@acme.com --owner-name "Jane Doe"

    python -m app.cli.admin list-tenants
"""

from __future__ import annotations

import typer
from sqlalchemy import select

from app.db.session import ProvisionerSessionLocal
from app.models import Tenant
from app.services.provisioning import AlreadyProvisioned, provision_tenant

app = typer.Typer(help="Platform-operator tools (internal use only).")


@app.command()
def provision(
    org: str = typer.Option(..., help="Organisation name"),
    slug: str = typer.Option(..., help="Unique org slug"),
    owner_email: str = typer.Option(..., help="First owner's email address"),
    owner_name: str = typer.Option(..., help="First owner's display name"),
) -> None:
    """Stand up a new tenant and invite its first owner (the de-facto admin)."""
    try:
        tenant_id, owner_id = provision_tenant(
            org_name=org,
            slug=slug,
            owner_email=owner_email,
            owner_name=owner_name,
        )
    except AlreadyProvisioned as e:
        typer.secho(f"Already provisioned: {e}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    typer.secho("Provisioned.", fg=typer.colors.GREEN)
    typer.echo(f"  tenant_id : {tenant_id}")
    typer.echo(f"  owner_id  : {owner_id}")
    typer.echo(f"  An invite email has been sent to {owner_email}.")


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