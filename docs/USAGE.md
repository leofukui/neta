# Usage Guide for NETA

This guide provides detailed instructions for setting up and using NETA, the WhatsApp-AI integration bridge.

## Initial Setup

### Environment Setup

1. **Create your environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Edit the `.env` file** with your specific configuration:
   ```
   # Required: Path to Chrome profile (create a dedicated profile)
   CHROME_PROFILE_PATH=/Users/your_username/Library/Application Support/neta-chrome-profile
   
   # Optional: Adjust timing parameters if needed
   RESPONSE_WAIT_TIME_TEXT=2
   RESPONSE_WAIT_TIME_IMAGE=5
   LOGIN_WAIT_DELAY=60
   ```

### WhatsApp Configuration

1. **Configure the WhatsApp chats**:
   - Create or rename your WhatsApp chats to match the names in your configuration file
   - For example, if your config has "Capivara" as a key, create a WhatsApp chat with that exact name

2. **Prepare chat contacts**:
   - Make sure all contacts/groups you want to use are already created in WhatsApp
   - Pin important chats to the top for easier access

### AI Platform Configuration

1. **Edit the config file** (`config/default.json` or create a custom one):
   ```json
   {
     "ai_mappings": {
       "Chat Name in WhatsApp": {
         "url": "https://ai-platform-url.com",
         "tab_name": "TabName",
         "input_selector": "CSS selector for input field",
         "response_selector": "CSS selector for response element"
       }
     }
   }
   ```

2. **Finding CSS selectors**:
   - Use browser DevTools to find the right selectors for each platform
   - For input fields, look for textareas or input elements
   - For responses, find the container that holds the AI's output

## Running NETA

### Basic Usage

```bash
# Using Poetry
poetry run neta

# Direct Python execution
python -m src.neta.main
```

### Advanced Usage

```bash
# With custom configuration
poetry run neta --config config/my_custom_config.json

# With different log settings
poetry run neta --log-level DEBUG --log-file logs/detailed.log
```

### First-time Login

1. When NETA first launches, it will open Chrome with multiple tabs:
   - WhatsApp Web
   - One tab for each configured AI platform

2. Log in to each platform manually:
   - Scan the WhatsApp QR code
   - Log in to each AI service with your credentials
   - Wait for the login delay to complete (default: 60 seconds)

3. After successful login, NETA will start monitoring chats automatically

## Daily Operation

### Starting the Application

1. Run NETA as described above
2. The browser will open with all tabs
3. Authentication should be preserved if using the same Chrome profile
4. If needed, re-authenticate to any logged out services

### Monitoring Operation

- Check the log file (`automation.log` by default) for operation details
- The terminal will also show log output while running

### Troubleshooting

If messages aren't being processed correctly:

1. **Check selectors**: AI platforms may update their UI, requiring selector updates
2. **Verify chat names**: Ensure WhatsApp chat names exactly match configuration keys
3. **Adjust timing**: Some AI services may require longer response times

## Advanced Configuration

### Custom Prompts

Edit the AI platform UI class to customize how prompts are formatted:

```python
# src/neta/ui/ai_platforms.py
prompt = f"Respond in 50 characters or fewer, if I ask for translation only give me it translated: {message}"
```

### Multiple Configurations

Create different configuration files for different use cases:

- `config/minimal.json`: Just one or two AI services
- `config/full.json`: All supported AI services
- `config/custom.json`: Special settings for particular needs

### Browser Profile Management

Creating a dedicated Chrome profile helps with:

1. **Persistent logins**: Avoid logging in each time
2. **Isolation**: Keep NETA activity separate from your normal browsing
3. **Customization**: Configure Chrome settings specifically for automation

## Maintenance

### Cache Management

The message cache prevents duplicate processing. If needed:

- Delete `data/.cache.json` to reset the cache
- Edit the file to remove specific entries

### Updating Selectors

When AI platforms update their UIs:

1. Use browser DevTools to identify new selectors
2. Update your configuration file
3. Restart NETA