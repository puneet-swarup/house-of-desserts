# 📡 Tailscale Remote Access Guide

How to give other people (or yourself on mobile) secure access to the House of Desserts app over the internet.

---

## What is Tailscale?

Tailscale is a **free, encrypted virtual network** that connects your devices as if they're on the same Wi-Fi — even when they're across the world.

**Key properties:**
- **Free** for up to 3 users / 100 devices
- **End-to-end encrypted** (WireGuard protocol)
- **No port forwarding** needed on your router
- **No public IP** needed
- **No domain name** needed
- Works on Windows, Mac, Linux, Android, iOS

**What it does NOT do:**
- Does NOT expose your app to the public internet
- Only people you **invite** (by adding their Tailscale account to your network) can access
- If your home PC is off, the app is unavailable

---

## Part 1: Setup on Your Home PC (One-Time)

### Step 1: Install Tailscale

1. Go to [tailscale.com/download/windows](https://tailscale.com/download/windows)
2. Download and run the installer
3. When prompted, click **"Log In"**
4. You'll see a URL in your browser → go to it
5. **Sign up** (free) using your Google, GitHub, or Microsoft account
6. After login, the Tailscale icon appears in your system tray (bottom-right, near the clock)
7. Click it → you should see **"Connected"** and an IP like `100.x.x.x`

### Step 2: Name Your Machine

1. Go to [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) in your browser
2. Find your PC in the list (it'll have a random name like "DESKTOP-ABC123")
3. Click the **three dots (⋯)** → **Edit machine name**
4. Type: `houseofdesserts`
5. Click **Save**

### Step 3: Enable MagicDNS

1. Go to [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns)
2. Toggle **MagicDNS** to **ON**
3. This gives every device a simple name (like `houseofdesserts`) instead of an IP

### Step 4: Configure Tailscale to Serve on Port 80

Open **PowerShell as Administrator** (right-click → "Run as administrator"):

```powershell
tailscale serve --bg 80
```
**What this does**: Tailscale listens on port 80 and forwards all traffic to your app running on port 8000. This means you can access the app at http://houseofdesserts (no port number needed).

**To verify**: Open a browser on your PC and go to http://houseofdesserts. You should see the dashboard.

**To stop serving later**: tailscale serve --unset

### Step 5: Make It Start on Boot (Optional)
To ensure tailscale serve runs after a PC restart:

1. Press Win + R → type shell:startup → Enter
2. Create a new file called tailscale-serve.bat with this content:
```commandline
echo off
tailscale serve --bg 80
```
3. Save it. Every time you log in to Windows, Tailscale serve will auto-start.

## Part 2: Access from Your Phone (One-Time)
### Step 1: Install Tailscale App
- *Android*: Play Store → search "Tailscale" → Install
- *iOS*: App Store → search "Tailscale" → Install
### Step 2: Sign In
1. Open the Tailscale app
2. Tap "Log In"
3. Use the same account you used on your PC
4. Wait for the app to show "Online" (green)
### Step 3: Access the App
1. Open your phone's browser (Chrome, Safari, etc.)
2. Type: http://houseofdesserts
3. You should see the House of Desserts dashboard 

**That's it**. No port number, no IP address, no configuration. Just the name.

### Using on Mobile Data (No Wi-Fi)
This works. Tailscale uses its own encrypted tunnel — it doesn't need your home Wi-Fi. As long as:

- Your phone has any internet connection (mobile data, café Wi-Fi, etc.)
- Tailscale app on your phone shows "Online"
- Your home PC is on and Tailscale is running

## Part 3: Giving Access to Other People
### How It Works
You can invite up to 2 additional people (3 total on the free tier) to your Tailscale network. Once invited, they can access http://houseofdesserts from any device, anywhere.

### Step 1: Create Tailscale Accounts for Them
Each person needs their own free Tailscale account:

- Go to tailscale.com → Sign Up (Google/GitHub/Microsoft)
### Step 2: Add Them to Your Tailnet
1. Go to login.tailscale.com/admin/members
2. Click "**Add member**"
3. Enter their email address (the one they used to sign up)
4. Click Send invitation
5. They'll get an email → click the link → accept
### Step 3: They Install Tailscale
On their device (phone, laptop, tablet):

1. Install the Tailscale app
2. Sign in with their account
3. Wait for "Online" status
### Step 4: They Access the App
Open browser → http://houseofdesserts → done.

### What They Can See
**Everything**. There's no user-level access control in the current app. Anyone with Tailscale access can:

- View all orders, customers, products
- Create/edit/delete records
- Print receipts, generate invoices
- Export data

**If you need role-based access** (e.g., "helper can only view, not delete"), that's a Phase 2 feature (user accounts + permissions).

### Removing Access
1. Go to login.tailscale.com/admin/members
2. Find the person → click "Remove"
3. They immediately lose access

### Part 4: Security Notes
| Concern | Answer |
|---------|--------|
| Is the connection encrypted? | Yes. WireGuard (military-grade). No one can sniff the traffic. |
| Can strangers find my app? | No. It's not on the public internet. Only Tailscale members can reach it. |
| What if my PC is compromised? | Tailscale doesn't reduce your PC's security. Keep Windows updated. |
| What if I forget to invite someone out? | Their access continues until you remove them. |
| Is there a monthly fee? | No. Free tier: 3 users, 100 devices, unlimited tailnets. |
| What if Tailscale service goes down? | Your app is unaffected (it's local). Remote access is down until Tailscale recovers. |

## Part 5: Troubleshooting
**"I can't connect from my phone"**

| Check | How |
|-------|-----|
| Tailscale on phone shows "Online"? | Open app → should say "Online" with a green dot |
| Tailscale on PC shows "Connected"? | Click tray icon → should say "Connected" |
| Same account on both? | Check [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) — both devices should be listed |
| MagicDNS enabled? | [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns) → MagicDNS = ON |
| `tailscale serve` running? | On PC: `tailscale status` in PowerShell → should show "serve" |
| PC is awake? | If PC is sleeping/hibernating, it's unreachable. Set Windows to "Never sleep" (Power Settings) |

**"CSS is broken / page looks unstyled"**
The pre-compiled CSS file is missing or outdated:
```
cd D:\puneet\Projects\house-of-desserts\app\static\css
.\tailwindcss.exe -i input.css -o app.css --minify
```

**"I get 'This site can't be reached'"**
- Make sure you're typing http://houseofdesserts (with http://, not https://)
- On iOS Safari, it may auto-try HTTPS. Type the full http:// prefix.
- Try http://houseofdesserts:80 explicitly

**"It was working, now it's not"**
1. Restart Tailscale on both devices (quit app → reopen)
2. On PC: tailscale down then tailscale up in PowerShell
3. Restart the uvicorn server
4. Check tailscale serve is still active: tailscale status

**"How do I change the machine name?"**
- login.tailscale.com/admin/machines → ⋯ → Edit machine name

**"Can I use a custom domain instead of 'houseofdesserts'?"**
- Yes, but you'd need to buy a domain (~₹800/year) and add a DNS record. Not necessary — the Tailscale name is fine.

## Part 6: Keeping Your PC Available 24/7
The app is only accessible when your PC is on and awake.

### Prevent Sleep
1. Settings → System → Power & Battery (Windows 11) or Settings → System → Power (Windows 10)
2. Screen: "Turn off after 10 minutes" (saves power, doesn't affect app)
3. Sleep: "Never" (critical — sleeping PC = unreachable app)
4. Plugged in / On battery: Set both to "Never" sleep
### Auto-Start the App After Reboot
1. Press Win + R → shell:startup → Enter
2. Create a file start-bakery.bat:
```
echo off
cd /d D:\puneet\Projects\house-of-desserts
.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```
3. Also ensure tailscale-serve.bat is in the same folder (from Part 1, Step 5)
### Alternative: Raspberry Pi
If you don't want your main PC running 24/7:

1. Buy a Raspberry Pi 4 (4GB) (~₹5,000)
2. Install Ubuntu Server
3. Copy the project over
4. Set up the same systemd service for auto-start
5. Uses 5W (vs. 40W+ for a laptop)
6. Silent, no fan (passive cooling)
## Quick Reference Card
| Task | Command / URL |
|------|--------------|
| Check Tailscale status (PC) | `tailscale status` |
| Start serving on port 80 | `tailscale serve --bg 8000` |
| Stop serving | `tailscale serve --unset` |
| Access from any device | `http://houseofdesserts` |
| Admin: manage machines | [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines) |
| Admin: manage members | [login.tailscale.com/admin/members](https://login.tailscale.com/admin/members) |
| Admin: DNS settings | [login.tailscale.com/admin/dns](https://login.tailscale.com/admin/dns) |
| Restart Tailscale (PC) | `tailscale down` → `tailscale up` |