#!/bin/bash
# E2E test: Verify that uploading two different images in the same editor
# session produces two distinct files on the server.
#
# Usage:
#   ./test_dual_image_upload.sh [base_url]
#
# Prerequisites:
#   - agent-browser installed and available in PATH
#   - Askbot dev server running (default: http://localhost:8000)
#   - Admin user with username=admin, password=admin123
#
# This test reproduces the duplicate-upload bug (askbot-master-pvt):
#   When two images are uploaded in the same editing session, the second
#   upload sends the first image's data because the ajaxFileUpload plugin
#   picks up a stale <input id="file-upload"> from the hidden first dialog.
#
# PASS: second upload returns a URL containing "test_image2"
# FAIL: second upload returns a URL containing "test_image1"

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

green() { printf '\033[32m%s\033[0m\n' "$1"; }
red()   { printf '\033[31m%s\033[0m\n' "$1"; }
bold()  { printf '\033[1m%s\033[0m\n' "$1"; }

assert_contains() {
    local label="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -q "$needle"; then
        green "  PASS: $label"
        PASS=$((PASS + 1))
    else
        red "  FAIL: $label (expected '$needle' in '$haystack')"
        FAIL=$((FAIL + 1))
    fi
}

assert_not_contains() {
    local label="$1" haystack="$2" needle="$3"
    if echo "$haystack" | grep -q "$needle"; then
        red "  FAIL: $label (did not expect '$needle' in '$haystack')"
        FAIL=$((FAIL + 1))
    else
        green "  PASS: $label"
        PASS=$((PASS + 1))
    fi
}

bold "=== Dual Image Upload E2E Test ==="
echo "Target: $BASE_URL"
echo ""

# Ensure clean session — log out any existing user
agent-browser open "$BASE_URL/account/signout/" > /dev/null 2>&1 || true

# ---- Step 1: Log in ----
bold "Step 1: Log in as admin"
agent-browser open "$BASE_URL/account/signin/" > /dev/null
agent-browser find placeholder "Username or email" fill "admin"
agent-browser find placeholder "Password" fill "admin123"
agent-browser eval "document.querySelector('input[name=login_with_password]').click()" > /dev/null
agent-browser wait --load networkidle

URL=$(agent-browser get url)
assert_not_contains "Logged in (redirected away from signin)" "$URL" "/account/signin/"

# ---- Step 2: Navigate to Ask page ----
bold "Step 2: Navigate to Ask Question page"
agent-browser open "$BASE_URL/questions/ask/" > /dev/null
agent-browser wait --load networkidle
URL=$(agent-browser get url)
assert_contains "On ask page" "$URL" "/ask/"

# ---- Step 3: Open image dialog and upload first image ----
bold "Step 3: Upload first image (test_image1.png)"

# Click the image button in the WMD toolbar
agent-browser eval "
    var imgBtn = document.getElementById('wmd-image-button');
    if (imgBtn) imgBtn.click();
    !!imgBtn;
" > /dev/null

sleep 1

# Verify dialog opened
DIALOG_COUNT=$(agent-browser eval "document.querySelectorAll('.file-upload-dialog').length")
assert_contains "Image upload dialog opened" "$DIALOG_COUNT" "1"

# Create a red 1x1 PNG and set it on the file input, trigger upload
agent-browser eval "
    var b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg==';
    var binary = atob(b64);
    var array = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i);
    var file = new File([array], 'test_image1.png', {type: 'image/png'});
    var dt = new DataTransfer();
    dt.items.add(file);
    var input = document.querySelector('.file-upload-dialog input[type=\"file\"]');
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    'triggered'
" > /dev/null

sleep 2

# Check that upload succeeded with correct filename
UPLOAD1_URL=$(agent-browser eval "
    var urlInput = document.querySelector('.file-upload-dialog:last-of-type input[type=text]');
    urlInput ? urlInput.value : 'NOT_FOUND';
")
# Strip quotes from eval output
UPLOAD1_URL=$(echo "$UPLOAD1_URL" | tr -d '"')

assert_contains "First upload URL contains test_image1" "$UPLOAD1_URL" "test_image1"
echo "  First upload URL: $UPLOAD1_URL"

# Click OK to accept
agent-browser eval "
    var btns = document.querySelectorAll('.file-upload-dialog:last-of-type .js-modal-footer button');
    btns[0].click(); // OK button
    'ok'
" > /dev/null

sleep 1

# Verify markdown was inserted
EDITOR_VAL=$(agent-browser eval "document.getElementById('editor').value")
assert_contains "Editor contains first image markdown" "$EDITOR_VAL" "test_image1"

# ---- Step 4: Check DOM state — stale dialog remains ----
bold "Step 4: Check for stale dialog DOM"
STALE_INPUT_COUNT=$(agent-browser eval "document.querySelectorAll('.file-upload-dialog input[type=\"file\"]').length")
echo "  File inputs in upload dialogs after first dialog close: $STALE_INPUT_COUNT"

# ---- Step 5: Open second image dialog and upload second image ----
bold "Step 5: Upload second image (test_image2.png)"

# Click image button again
agent-browser eval "
    var imgBtn = document.getElementById('wmd-image-button');
    if (imgBtn) imgBtn.click();
    !!imgBtn;
" > /dev/null

sleep 1

# Check for duplicate IDs (this IS the bug)
DUP_COUNT=$(agent-browser eval "document.querySelectorAll('.file-upload-dialog input[type=\"file\"]').length")
DUP_COUNT=$(echo "$DUP_COUNT" | tr -d '"')
echo "  File inputs in upload dialogs after second dialog open: $DUP_COUNT"

if [ "$DUP_COUNT" = "1" ]; then
    green "  OK: Only one upload dialog in DOM (stale dialog was cleaned up)"
else
    red "  BUG: $DUP_COUNT upload dialog file inputs in DOM (stale dialog not removed)"
fi

# Create a blue 1x1 PNG as test_image2.png and set it on the VISIBLE input
agent-browser eval "
    var b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg==';
    var binary = atob(b64);
    var array = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) array[i] = binary.charCodeAt(i);
    var file = new File([array], 'test_image2.png', {type: 'image/png'});
    var dt = new DataTransfer();
    dt.items.add(file);

    // Find the current dialog's file input
    var inputs = document.querySelectorAll('.file-upload-dialog input[type=\"file\"]');
    var input = inputs[inputs.length - 1];
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    'triggered on input index ' + (inputs.length - 1);
" > /dev/null

sleep 2

# ---- Step 6: THE KEY CHECK — what did the server return? ----
bold "Step 6: Verify second upload result"
UPLOAD2_URL=$(agent-browser eval "
    var dialogs = document.querySelectorAll('.file-upload-dialog');
    var lastDialog = dialogs[dialogs.length - 1];
    var urlInput = lastDialog.querySelector('input[type=text]');
    urlInput ? urlInput.value : 'NOT_FOUND';
")
UPLOAD2_URL=$(echo "$UPLOAD2_URL" | tr -d '"')

echo "  Second upload URL: $UPLOAD2_URL"

assert_contains "Second upload URL contains test_image2" "$UPLOAD2_URL" "test_image2"
assert_not_contains "Second upload URL does NOT contain test_image1" "$UPLOAD2_URL" "test_image1"

# Also check the label text
UPLOAD2_LABEL=$(agent-browser eval "
    var dialogs = document.querySelectorAll('.file-upload-dialog');
    var lastDialog = dialogs[dialogs.length - 1];
    var label = lastDialog.querySelector('label');
    label ? label.textContent : 'NOT_FOUND';
")
UPLOAD2_LABEL=$(echo "$UPLOAD2_LABEL" | tr -d '"')
echo "  Second upload label: $UPLOAD2_LABEL"
assert_contains "Label shows test_image2" "$UPLOAD2_LABEL" "test_image2"

# Take screenshot
agent-browser screenshot /tmp/test_dual_upload_result.png > /dev/null 2>&1 || true

# Click Cancel to close
agent-browser eval "
    var dialogs = document.querySelectorAll('.file-upload-dialog');
    var lastDialog = dialogs[dialogs.length - 1];
    var btns = lastDialog.querySelectorAll('.js-modal-footer button');
    btns[1].click(); // Cancel button
    'cancelled'
" > /dev/null

# Log out to leave clean state
agent-browser open "$BASE_URL/account/signout/" > /dev/null 2>&1 || true

# ---- Summary ----
echo ""
bold "=== Results ==="
green "  Passed: $PASS"
if [ "$FAIL" -gt 0 ]; then
    red "  Failed: $FAIL"
    echo ""
    red "VERDICT: FAIL — Second image upload reuses first image's file (bug present)"
    exit 1
else
    echo "  Failed: $FAIL"
    echo ""
    green "VERDICT: PASS — Both images uploaded correctly with distinct files"
    exit 0
fi
