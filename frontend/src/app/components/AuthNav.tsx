"use client";

/**
 * AuthNav — Clerk sign-in / user profile button in the top navbar.
 * Renders nothing when Clerk is not configured (NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
 * is empty), so the app works in demo mode without auth setup.
 */
import { SignedIn, SignedOut, UserButton, SignInButton } from "@clerk/nextjs";

const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export function AuthNav() {
  if (!clerkEnabled) return null;

  return (
    <div className="flex items-center gap-3">
      <SignedOut>
        <SignInButton mode="modal">
          <button className="text-sm px-3 py-1.5 rounded border border-slate-600 text-slate-300 hover:border-slate-400 hover:text-white transition-colors">
            Sign in
          </button>
        </SignInButton>
      </SignedOut>
      <SignedIn>
        <UserButton
          appearance={{
            elements: {
              avatarBox: "w-8 h-8",
            },
          }}
        />
      </SignedIn>
    </div>
  );
}
