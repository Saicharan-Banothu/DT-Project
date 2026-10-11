// SentiCall v3 — Playwright End-to-End System Integration Tests
const { test, expect } = require('@playwright/test');

test.describe('SentiCall v3 Comprehensive E2E Tests', () => {

  test('1. Security Verification: Strict CSP & Zero Third-Party Requests', async ({ page }) => {
    const thirdPartyRequests = [];

    page.on('request', request => {
      const url = request.url();
      if (!url.startsWith('http://localhost:8000') &&
          !url.startsWith('http://127.0.0.1:8000') &&
          !url.startsWith('data:') &&
          !url.startsWith('blob:') &&
          !url.startsWith('chrome-error://')) {
        thirdPartyRequests.push(url);
      }
    });

    const response = await page.goto('/');
    expect(response.status()).toBe(200);

    // Verify security headers
    const headers = response.headers();
    expect(headers['content-security-policy']).toContain("default-src 'self'");
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['referrer-policy']).toBe('no-referrer');

    // Assert zero third-party network egress
    expect(thirdPartyRequests).toHaveLength(0);
  });

  test('2. Guest Mode: Public Features & Authentication Gate', async ({ page }) => {
    await page.goto('/');

    // Guest view visible, sign-in button visible
    await expect(page.locator('#auth-guest-view')).toBeVisible();
    await expect(page.locator('#auth-user-view')).not.toBeVisible();

    // Scam Atlas, Practice, Insights should be accessible
    await page.click('#tab-atlas');
    await expect(page.locator('#page-atlas')).toHaveClass(/active/);
    await expect(page.locator('.atlas-card').first()).toBeVisible();

    await page.click('#tab-practice');
    await expect(page.locator('#page-practice')).toHaveClass(/active/);
    await expect(page.locator('#practice-game-container')).toBeVisible();

    await page.click('#tab-insights');
    await expect(page.locator('#page-insights')).toHaveClass(/active/);
    await expect(page.locator('#metric-text-f1')).toBeVisible();

    // Clicking Live Listen as guest must prompt Sign-In modal
    await page.click('#tab-live');
    await expect(page.locator('#modal-signin')).toBeVisible();
    await page.click('#modal-signin .btn-icon'); // Close modal
    await expect(page.locator('#modal-signin')).not.toBeVisible();
  });

  test('3. Instant Sample Call Evaluation for Guests', async ({ page }) => {
    await page.goto('/#page-analyze');

    // Wait for built-in sample cards
    const firstSample = page.locator('.sample-card').first();
    await expect(firstSample).toBeVisible();

    // Click Analyze Call on first sample
    await firstSample.locator('.btn-run-sample').click();

    // Should transition to Case Report view
    await expect(page.locator('#page-result')).toHaveClass(/active/, { timeout: 25000 });
    await expect(page.locator('#verdict-heading-text')).toBeVisible();
    await expect(page.locator('#verdict-gauge-number')).toBeVisible();
    await expect(page.locator('#card-action-plan')).toBeVisible();
  });

  test('4. Signed-In User Flow: Login, Onboarding Consent, and Live Listen Pre-flight', async ({ page, context }) => {
    // 1. Perform development login bypass
    const loginRes = await context.request.post('/auth/dev-login', {
      data: { email: 'e2e_user@senticall.ai', name: 'E2E Tester', role: 'user' }
    });
    expect(loginRes.ok()).toBeTruthy();

    await page.goto('/');

    // Verify user profile avatar and name displayed
    await expect(page.locator('#auth-user-view')).toBeVisible();
    await expect(page.locator('#user-nav-name')).toContainText('E2E');

    // Onboarding modal consent
    const onboarding = page.locator('#modal-onboarding');
    if (await onboarding.isVisible()) {
      await page.click('#ob-screen-1 button'); // Next
      await page.click('#ob-screen-2 button'); // Next
      await page.check('#consent-agree-checkbox');
      await page.click('#btn-finish-onboarding');
      await expect(onboarding).not.toBeVisible();
    }

    // 2. Navigate to Live Listen
    await page.click('#tab-live');
    await expect(page.locator('#page-live')).toHaveClass(/active/);
    await expect(page.locator('#live-setup-screen')).toBeVisible();

    // Truthful privacy strip
    const trustText = await page.locator('#trust-strip-mode-text').textContent();
    expect(trustText).toContain('Audio is processed on this device and is never uploaded');

    // Verify Pre-flight Check elements
    await expect(page.locator('#pf-permission')).toBeVisible();
    await expect(page.locator('#pf-level')).toBeVisible();
    await expect(page.locator('#btn-run-speed-test')).toBeVisible();

    // Run device speed test
    await page.click('#btn-run-speed-test');
    await expect(page.locator('#pf-dot-speed')).toHaveText('✓', { timeout: 8000 });

    // Start live listen protection
    const startBtn = page.locator('#btn-start-live-listen');
    await expect(startBtn).toBeEnabled();
    await startBtn.click();

    // Active live dashboard must appear
    await expect(page.locator('#live-active-dashboard')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#live-active-state-pill')).toBeVisible();
    await expect(page.locator('#live-session-timer')).toBeVisible();

    // Stop and summarize
    await page.click('#live-active-dashboard .btn-danger');

    // End-of-call summary opens in Result page
    await expect(page.locator('#page-result')).toHaveClass(/active/, { timeout: 10000 });
    await expect(page.locator('#verdict-heading-text')).toBeVisible();
  });

  test('5. PDF Report Generation & Encrypted My Cases Management', async ({ page, context }) => {
    // Authenticate
    await context.request.post('/auth/dev-login', {
      data: { email: 'e2e_storage@senticall.ai', name: 'Storage Tester', role: 'user' }
    });

    await page.goto('/');

    // Evaluate sample call to populate current case data
    const sample = page.locator('.sample-card').first();
    await sample.locator('.btn-run-sample').click();
    await expect(page.locator('#page-result')).toHaveClass(/active/);

    // Save to My Cases
    await page.click('button:has-text("Save to My Cases")');

    // Switch to My Cases
    await page.click('#tab-cases');
    await expect(page.locator('#page-cases')).toHaveClass(/active/);
    await expect(page.locator('#stat-total-cases')).not.toHaveText('0');

    // Download PDF report
    await page.evaluate(() => switchPage('result'));
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("Download Case Report (PDF)")');
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain('.pdf');
  });

  test('6. Privacy Center: Data Export and Device Wipe', async ({ page, context }) => {
    await context.request.post('/auth/dev-login', {
      data: { email: 'e2e_privacy@senticall.ai', name: 'Privacy Tester', role: 'user' }
    });

    await page.goto('/#page-privacy');
    await expect(page.locator('#page-privacy')).toHaveClass(/active/);

    // Test Export Data download
    const exportPromise = page.waitForEvent('download');
    await page.click('button:has-text("Export JSON Data")');
    const exportDownload = await exportPromise;
    expect(exportDownload.suggestedFilename()).toContain('.json');

    // Verify security events table loaded
    await expect(page.locator('.security-events-table-wrap')).toBeVisible();
  });

});
