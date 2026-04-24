# e-OSEWS Mobile App (Expo)

Mobile starter app for the e-OSEWS backend.

## Included
- Login using `/api/auth/login`
- Token persistence via AsyncStorage
- Summary fetch from `/api/summary`
- Event submission to `/api/events`
- Branding assets for splash/icon (`logo1.png`, `icon.png`, `adaptive-icon-foreground.png`)
- Expo SDK 54-compatible dependencies

## Runtime requirements
- Node.js `20.19.4` to `<25` (Node 22 LTS recommended)
- npm `10+`

## Run
1. In this folder, install:
   - `npm install`
2. Start Expo:
   - `npm run start`
3. Open on Android emulator/device.

## Backend URL
Configured in `src/api/client.js`:
- `http://10.0.2.2:8000` (Android emulator)

If testing on a physical phone, replace with your PC local network IP, e.g.:
- `http://192.168.1.72:8000`
