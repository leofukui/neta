# NETA Architecture

This document outlines the architecture of the NETA application, which bridges WhatsApp chats with AI platforms.

## System Overview

NETA is designed as a modular Python application that connects WhatsApp Web with various AI chat platforms. It monitors WhatsApp chats for new messages, processes them with the appropriate AI model, and returns the responses to the original chat.

```
+----------------+     +----------------+     +----------------+
|                |     |                |     |                |
|   WhatsApp     |---->|     NETA      |---->|   AI Platforms |
|     Web        |     |  Application   |     | (GPT, Claude,  |
|                |<----|                |<----| Perplexity...) |
+----------------+     +----------------+     +----------------+
```

## Core Components

### 1. `NetaAutomation` (Core Controller)

This is the main controller class that orchestrates the entire application flow. It:
- Initializes all components
- Manages the main event loop
- Coordinates interactions between WhatsApp and AI platforms
- Handles message processing and response routing

### 2. Browser Management

The `BrowserManager` handles browser initialization and tab management:
- Creates a Chrome browser instance with appropriate settings
- Manages tabs for WhatsApp and AI platforms
- Provides methods for switching between tabs

### 3. UI Interaction

UI interaction is divided into specific components:
- `WhatsAppUI`: Handles WhatsApp Web interface interactions
  - Selecting chats
  - Detecting new messages (text and images)
  - Sending responses

- `AIPlatformUI`: Manages interactions with AI platforms
  - Sending text prompts
  - Uploading and describing images
  - Extracting responses

### 4. Configuration and Utilities

- `Config`: Loads and provides access to configuration settings
- `MessageCache`: Prevents duplicate processing of messages
- `ImageManager`: Handles temporary image storage and cleanup
- `Logger`: Provides consistent logging throughout the application

## Data Flow

1. **Message Detection**:
   - Application monitors WhatsApp Web for new incoming messages
   - When a message is detected, it's checked against the cache to prevent duplicate processing

2. **AI Processing**:
   - Based on the chat name, the message is routed to the appropriate AI platform
   - Text messages are sent directly; images are first downloaded then uploaded to the AI
   - The application waits for and extracts the AI's response

3. **Response Delivery**:
   - The AI response is sent back to the original WhatsApp chat
   - The response is cached to prevent future duplication

## Extension Points

The architecture is designed for extensibility:

1. **New AI Platforms**:
   - Add new platform configurations to the JSON config file
   - The application will automatically handle them without code changes

2. **Message Processing Enhancements**:
   - Modify prompt templates in the AI platform UI classes
   - Add pre-processing or post-processing steps in the automation class

3. **UI Interaction Improvements**:
   - The UI interaction classes can be updated to handle changes in web interfaces
   - Selector configurations allow adapting to UI changes without code modification

## Dependencies

- **Selenium**: Browser automation and element interaction
- **WebDriver Manager**: Chrome driver management
- **PyperClip**: Clipboard operations for reliable text input
- **Python-dotenv**: Environment variable management