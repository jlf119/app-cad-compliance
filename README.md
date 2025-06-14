# GLTF Viewer for Onshape (Python + Vercel)

This application demonstrates:
- How to fetch a glTF representation of an Onshape model
- How to create an app that runs as a tab inside an Onshape document
- OAuth2 authentication
- Use of REST APIs
- Use of document context

The backend is written in Python and deployed on Vercel. The frontend is static and served from the `public/` and `web/` directories.

## Prerequisites

1. Install the following software:
    - Git
    - Python 3.8+
    - [Vercel CLI](https://vercel.com/docs/cli)
    - (Optional) Docker (for local testing)
2. Make sure you have a [GitHub](https://github.com) account.

## Clone the Repository

```bash
git clone https://github.com/<your-github-username>/app-cad-compliance.git
cd app-cad-compliance
```

## Configure Environment Variables

Create a `.env` file in the root directory with the following variables:

```
API_URL=https://cad.onshape.com/api
OAUTH_CALLBACK_URL=https://<your-vercel-domain>/api/oauthRedirect
OAUTH_CLIENT_ID=<client-id-from-onshape-dev-portal>
OAUTH_CLIENT_SECRET=<client-secret-from-onshape-dev-portal>
OAUTH_URL=https://oauth.onshape.com
WEBHOOK_CALLBACK_ROOT_URL=https://<your-vercel-domain>/
SESSION_SECRET=<a-cryptographically-secure-string>
```

- Replace `<your-vercel-domain>` with your deployed Vercel domain (e.g., `app-cad-compliance.vercel.app`).
- Replace the client ID and secret with values from your Onshape OAuth app.

## Onshape OAuth App Setup

1. Go to https://dev-portal.onshape.com/signin and log in.
2. Create a new OAuth application:
    - Name: `gltf-viewer-yourname`
    - Primary format: `com.yourname.gltf-viewer`
    - Redirect URLs: `https://<your-vercel-domain>/api/oauthRedirect`
    - OAuth URL: `https://<your-vercel-domain>/api/oauthSignin`
    - Set permissions as needed (read/write documents, profile info)
3. Save the client ID and secret for your `.env` file.

## Onshape App Store Entry & Extension

1. Create a Store entry for your app in the Onshape developer portal.
2. Add an extension:
    - Name: `gltf-viewer`
    - Location: `Element tab`
    - Action URL: `https://<your-vercel-domain>`

## Local Development

1. Install Python dependencies:

```bash
pip install -r api/requirements.txt
```

2. (Optional) Test the API locally:

```bash
vercel dev
```

- The API will be available at `http://localhost:3000/api/` by default.

## Deploy to Vercel

1. Log in to Vercel:

```bash
vercel login
```

2. Deploy:

```bash
vercel --prod
```

- Follow the prompts to link or create a Vercel project.
- Set your environment variables in the Vercel dashboard under **Project Settings > Environment Variables**.

## Using the GLTF Viewer in Onshape

1. Open an Onshape document with at least one Part.
2. Click the **+** button in the bottom-left, then **Applications > gltf-viewer**.
3. Authorize the application when prompted.
4. Select an Element from the dropdown and wait for the viewer to load.

**Controls:**
- Zoom: Mouse wheel
- Rotate: Left-click and drag
- Pan: Right-click and drag

If you encounter issues loading or rendering, check your browser's JavaScript console for errors.

---

You can refer to your repository to see how the app handles authentication and API integration. For further customization, edit the Python backend in `api/` and the frontend in `public/` and `web/`.

