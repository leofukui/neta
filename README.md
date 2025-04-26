# NETA - WhatsApp-AI Chat Integration Bridge

NETA is a Python application that integrates WhatsApp with various AI platforms, allowing you to automatically process messages from WhatsApp chats with different AI models and return their responses.

## Features

- Connect WhatsApp Web with multiple AI platforms (ChatGPT, Claude, Gemini, Perplexity, Grok)
- Process both text and image messages
- Maintain separate AI model mappings for different WhatsApp chats
- Caching system to prevent duplicate responses
- Automatic temp file management
- Configurable response formatting

## Setup

### Prerequisites

- Python 3.10+
- Poetry (dependency management)
- Chrome browser

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/neta.git
   cd neta
   ```

2. **Install dependencies with Poetry**:
   ```bash
   poetry install
   ```

3. **Create environment configuration**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` file to set your Chrome profile path and other configurations.

4. **Configure AI mappings**:
   The `config/` directory contains JSON configuration files that map WhatsApp chat names to AI platforms.
   Edit these files to match your WhatsApp chat names and add any specific selectors needed.

## Usage

```bash
# Run with default configuration
poetry run neta

# Run with specific configuration file
poetry run neta --config config/full.json

# Set logging level and output file
poetry run neta --log-level DEBUG --log-file logs/debug.log
```

### Configuration

- `config/default.json`: Basic configuration with ChatGPT and Perplexity
- `config/full.json`: Full configuration with all supported AI platforms
- `.env`: Environment variables for paths and timing configurations

### WhatsApp Setup

1. Make sure your WhatsApp chats match the names in your configuration file
2. When the application launches, you'll need to scan the QR code to log in to WhatsApp Web
3. You'll also need to log in to each AI platform in their respective tabs

## Project Structure

```
neta/
├── config/                 # Configuration files
├── src/
│   └── neta/
│       ├── api/            # External API integrations
│       ├── core/           # Core application logic
│       ├── ui/             # UI interaction components
│       └── utils/          # Utility functions
├── tests/                  # Test suite
├── .env.example            # Example environment variables
├── pyproject.toml          # Poetry configuration
└── README.md               # Documentation
```

## Customization

### Adding New AI Platforms

1. Add the platform configuration to your JSON config file:
   ```json
   "New Platform": {
     "url": "https://new-platform.ai/",
     "tab_name": "NewAI",
     "input_selector": "input.selector-for-text-input",
     "response_selector": "div.selector-for-responses"
   }
   ```

2. Test the selectors by running the application and checking the logs.

### Troubleshooting

- Check `automation.log` for detailed error messages
- If AI platform HTML structure changes, update the CSS selectors in your config file
- For image handling issues, adjust timing parameters in the `.env` file

## License

This project is licensed under the MIT License - see the LICENSE file for details.