# Local authentication

GrowMaster requires one local administrator account. On the first visit, the application asks for a display name and password. Every business-data API, including exports, invoices and backups, is unavailable until authentication succeeds.

## Password storage

The backend never stores the original password. It derives a hash with Python's `scrypt` implementation, a unique random 16-byte salt and constant-time verification. Passwords must contain at least 12 characters, one letter and one digit.

The administrator credential and authentication sessions are stored in separate database tables. Portable and automatic backups exclude both tables. A restored business-data backup therefore cannot reveal or replace the administrator password and cannot create a logged-in browser.

## Sessions

Successful setup or login creates a cryptographically random token. Only its SHA-256 digest is stored in the database. The browser receives the token in a 30-day cookie with `HttpOnly`, `SameSite=Strict` and path `/`; JavaScript cannot read it. Logout removes both the stored session and browser cookie. Expired sessions are rejected and removed, and only the ten newest sessions are retained.

Five failed login attempts from the same client trigger a five-minute cooldown. Login errors do not expose password hashes or session tokens.

## Account settings

The **Nastavitve** screen shows the administrator name, active-session count and session lifetime. Changing the display name requires the current password. Changing the password requires the current password plus a different strong password.

A password change deletes every existing session before creating one replacement session for the current browser. Other browsers and devices immediately lose access. The same five-attempt cooldown protects current-password confirmation.

## Local HTTP and HTTPS

The default Docker setup is intended for the same computer and uses `COOKIE_SECURE=false` because `http://localhost` has no TLS. Do not publish ports 3000, 8000 or 5432 directly to the internet.

If GrowMaster is exposed to other devices, place it behind an HTTPS reverse proxy, restrict network access, set `COOKIE_SECURE=true`, and use a trusted certificate. The frontend and API origins must remain explicitly allowed by the backend CORS configuration.

There is deliberately no unauthenticated password-reset endpoint. Keep the administrator password in a trusted password manager before entering production data.
