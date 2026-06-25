"use client";

import { useState } from "react";
import { Dialog, Button } from "@irontrust/ui";
import { useInviteMember } from "@/lib/members";

interface InviteDialogProps {
  open: boolean;
  onClose: () => void;
}

export function InviteDialog({ open, onClose }: InviteDialogProps) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const invite = useInviteMember();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    invite.mutate(
      { email: email.trim(), name: name.trim() },
      {
        onSuccess: () => {
          setEmail("");
          setName("");
          onClose();
        },
      }
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => { if (!o) onClose(); }}
      title="Invite member"
    >
      <form onSubmit={handleSubmit} className="mt-4 min-w-80 space-y-4">
        <div className="space-y-1">
          <label htmlFor="invite-name" className="text-sm font-medium text-ink">
            Full name
          </label>
          <input
            id="invite-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border-hairline bg-surface text-ink focus:ring-brand w-full rounded-md border px-3 py-2 text-sm focus:ring-1 focus:outline-none"
            placeholder="Jane Smith"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="invite-email" className="text-sm font-medium text-ink">
            Email address
          </label>
          <input
            id="invite-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="border-hairline bg-surface text-ink focus:ring-brand w-full rounded-md border px-3 py-2 text-sm focus:ring-1 focus:outline-none"
            placeholder="jane@example.com"
          />
        </div>
        {invite.isError && (
          <p className="text-danger text-sm" role="alert">
            {(invite.error as Error)?.message ?? "Invite failed. Please try again."}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={invite.isPending}>
            {invite.isPending ? "Inviting…" : "Send invite"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
