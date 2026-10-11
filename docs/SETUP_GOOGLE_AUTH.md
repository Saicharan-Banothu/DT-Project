# Google OAuth 2.0 & Production Database Setup Guide

This guide walks you through setting up Google Sign-In and an external free PostgreSQL database for SentiCall v3 on Render.

---

## 1. Create Google Cloud OAuth Credentials

### Step 1: Create a Google Cloud Project
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown in the top bar and select **New Project**.
3. Name the project `SentiCall` and click **Create**.
4. Make sure your new project is selected in the top bar.

### Step 2: Configure the OAuth Consent Screen
1. In the left navigation menu, go to **APIs & Services** > **OAuth consent screen**.
2. Select **External** user type and click **Create**.
3. Under **App information**:
   - **App name**: `SentiCall`
   - **User support email**: Select your email address.
   - **App logo**: (Optional).
4. Under **Authorized domains**:
   - *Note on Render free subdomain:* If Google Cloud Console displays an error attempting to add `onrender.com` as a top-level authorized domain, **leave Authorized domains empty**. Google allows redirect URIs to subdomains without requiring top-level domain registration for basic scopes.
5. Under **Developer contact information**:
   - Enter your email address.
   - Click **Save and Continue**.
6. Under **Scopes**:
   - Click **Add or Remove Scopes**.
   - Select only the three fundamental OpenID scopes:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `openid`
   - **Important:** Do *NOT* select any Gmail, Google Drive, Google Contacts, or offline access scopes. SentiCall adheres strictly to minimal privileges.
   - Click **Update** and then **Save and Continue**.
7. Under **Publishing status**:
   - Click **Publish App** to switch from Testing to In Production.
   - Confirm when prompted. This allows any standard Google account to sign in. (Verification by Google is NOT required because SentiCall only uses non-sensitive basic identity scopes).

### Step 3: Create OAuth 2.0 Client ID
1. In the left menu, click **Credentials**.
2. Click **+ Create Credentials** at the top and select **OAuth client ID**.
3. Under **Application type**, choose **Web application**.
4. Set **Name** to `SentiCall Web Client`.
5. Under **Authorized JavaScript origins**, add:
   - `https://senticall-v2.onrender.com`
   - `http://localhost:8000`
6. Under **Authorized redirect URIs**, add:
   - `https://senticall-v2.onrender.com/auth/google/callback`
   - `http://localhost:8000/auth/google/callback`
7. Click **Create**.
8. A modal will appear showing your **Client ID** and **Client Secret**. Keep this window open or copy them securely.

---

## 2. Set Up Free Production PostgreSQL Database

SentiCall stores only identity, session tokens, consent records, and security audit logs on the server. Call content and transcripts are never stored in the database.

Recommended free external Postgres providers:
- **Neon Serverless Postgres** ([https://neon.tech](https://neon.tech)) — 0.5 GB free storage, instant branching.
- **Supabase** ([https://supabase.com](https://supabase.com)) — 500 MB free database tier.

### Setup Steps (using Neon):
1. Sign up at [neon.tech](https://neon.tech).
2. Click **Create Project** (e.g. `senticall-db`).
3. Select region matching Render (e.g., `US East (Ohio)` or `US West (Oregon)`).
4. Copy the connection string. It will look like:
   ```
   postgresql://senticall_owner:password@ep-cool-fog-12345.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

---

## 3. Configure Render Environment Variables

1. Log into your [Render Dashboard](https://dashboard.render.com/).
2. Select your `senticall-v2` Web Service.
3. In the left navigation, click **Environment**.
4. Set the following environment variables:

| Key | Value / Source | Description |
|---|---|---|
| `ENV` | `production` | Enables strict production fail-closed security guards |
| `PUBLIC_BASE_URL` | `https://senticall-v2.onrender.com` | Base URL used for OAuth callbacks and CSRF origin verification |
| `GOOGLE_CLIENT_ID` | `YOUR_GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | `YOUR_GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `SESSION_SECRET` | *(Click "Generate" in Render or 64-char hex)* | Used for cryptographic session signing and state entropy |
| `DATABASE_URL` | `postgresql://...` | Connection string from Neon or Supabase |
| `ADMIN_EMAILS` | `your-email@gmail.com` | Comma-separated emails granted Admin Health dashboard access |
| `DEV_LOGIN_BYPASS` | `false` | Must remain `false` in production (server refuses to start if true) |

5. Click **Save Changes**. Render will automatically trigger a deployment.

---

## 4. Cold Starts & Free Tier Behavior

- On Render's free tier, the web service spins down after 15 minutes of inactivity.
- The first request after spin-down may take 30–50 seconds to complete while the container launches.
- **Tip for Demos:** Ping `https://senticall-v2.onrender.com/healthz` 1–2 minutes before presenting to wake up the server.
