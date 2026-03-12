#!/usr/bin/env bash
# PWA → TWA (APK Android) Build Script
# Run this script interactively — it will prompt for passwords and settings.
#
# Prerequisites:
#   npm install -g @bubblewrap/cli
#
# Usage:
#   ./scripts/build-apk.sh init    # First time setup
#   ./scripts/build-apk.sh build   # Rebuild APK
#   ./scripts/build-apk.sh fingerprint  # Show SHA256 for assetlinks.json

set -euo pipefail
cd "$(dirname "$0")/.."

TWA_DIR="twa"
MANIFEST_URL="https://ai-nutrition-frontend-78p7.onrender.com/manifest.json"

case "${1:-help}" in
  init)
    echo "=== Initializing TWA project ==="
    echo ""
    echo "Bubblewrap will prompt you for:"
    echo "  - Application ID: com.ainutrition.app"
    echo "  - Keystore location: ./android.keystore"
    echo "  - Key alias: nutriai"
    echo "  - Passwords: use the SAME password for keystore and key"
    echo ""
    echo "It will also download JDK 17 + Android SDK (~500MB) on first run."
    echo ""
    mkdir -p "$TWA_DIR"
    cd "$TWA_DIR"
    bubblewrap init --manifest="$MANIFEST_URL"
    ;;
  build)
    echo "=== Building APK ==="
    cd "$TWA_DIR"
    bubblewrap build
    echo ""
    echo "Output files:"
    ls -lh app-release-signed.apk app-release-bundle.aab 2>/dev/null
    echo ""
    echo "To install on device:"
    echo "  cp $TWA_DIR/app-release-signed.apk /mnt/c/Users/meuze/Downloads/NutriAI.apk"
    echo "  Then transfer NutriAI.apk to your phone"
    ;;
  fingerprint)
    echo "=== SHA256 Fingerprint ==="
    cd "$TWA_DIR"
    keytool -list -v -keystore android.keystore -alias nutriai 2>/dev/null | grep SHA256
    echo ""
    echo "Copy this fingerprint to frontend/public/.well-known/assetlinks.json"
    ;;
  *)
    echo "Usage: $0 {init|build|fingerprint}"
    echo ""
    echo "  init        Initialize TWA project (first time)"
    echo "  build       Build APK from existing project"
    echo "  fingerprint Show SHA256 for assetlinks.json"
    ;;
esac
