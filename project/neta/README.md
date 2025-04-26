# WhatsApp AI Automation

A Python project to automate interactions between WhatsApp Web and AI chatbots using Playwright.

## Setup

1. **Install Poetry**:

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:

   ```bash
   poetry install
   ```

3. **Install Playwright browsers**:

   ```bash
   poetry run playwright install
   ```

4. **Configure**:
   - Edit `config.json` with correct URLs and selectors for AI platforms.
   - Ensure group names in WhatsApp match the keys in `ai_mappings`.

5. **Run the project**:

   ```bash
   poetry run python main.py
   ```

## Notes

- Log in manually to each platform when prompted.
- Update selectors in `config.json` based on actual DOM elements (use browser DevTools).
- The project polls WhatsApp every 5 seconds; adjust as needed.
- Logs are saved to `automation.log`.

## Troubleshooting

- If a tab fails to load, check the URL and network connection.
- If interactions fail, verify selectors using browser DevTools.
- For WhatsApp, ensure the chat is active and focused.