# Android ARM64 Testing

GitHub Actions workflow untuk menjalankan Android 12 ARM64 dengan web interface custom.

## Features

- 🤖 Android 12 ARM64 native
- 📱 Upload & install APK via web
- 🚀 Launch/uninstall apps
- 🖥️ Shell command execution
- 📋 Logcat viewer
- 📸 Screenshot capture
- 🌐 Cloudflare Tunnel access

## Usage

1. Push ke GitHub
2. Actions → "Android ARM64 Testing" → Run workflow
3. Tunggu 3 menit
4. Copy URL dari log
5. Buka di browser
6. Upload APK dengan drag & drop

## Web Interface

- Upload APK (drag & drop atau click)
- View installed apps
- Launch/uninstall apps
- Execute shell commands
- View logcat
- Take screenshots

## Requirements

- GitHub Actions dengan ARM64 runner (ubuntu-24.04-arm64)
- Atau self-hosted ARM64 runner
