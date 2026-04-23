# Test Fixtures

This directory contains offline fixtures used for testing the Neuzelaar browser.

## Requirements for Fixtures

1. **Offline:** Fixtures must not depend on any external network resources. Any "external" resources should be referenced via local paths or mocked where necessary.
2. **Stable:** Fixtures should be simple and not change unexpectedly. Hand-written HTML is preferred over saved copies of live sites to keep them minimal and focused.
3. **Small:** Keep files as small as possible to ensure tests run quickly and are easy to debug.

## Directory Structure

- `sites/`: Contains HTML files representing various test pages.
