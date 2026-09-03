# Werewolf Game: AI Simulation Platform

This project is a comprehensive, AI-powered simulation of the social deduction game "Werewolf" (also known as Mafia). It serves as a robust platform for developing and testing AI agent behaviors, game theory strategies, and complex, multi-agent interactions in a dynamic environment.

The simulation is built with a clean architecture, separating the core game logic from the AI controllers and the user interface, allowing for modular development and testing.

## Key Features

*   **Modular Game Engine**: A state-machine-driven engine that manages all game phases, rules, and player interactions.
*   **Diverse Character Roles**: Supports a wide range of classic and custom roles, each with unique abilities:
    *   **Good Faction**: Villager, Seer, Witch, Guard, Hunter.
    *   **Evil Faction**: Werewolf, Black Werewolf King.
*   **Advanced Game Flow**:
    *   **Night Phase**: Secret actions are performed (Werewolf kills, Seer inspects, etc.).
    *   **Day Phase**: Public discussion, nominations, and voting for execution.
    *   **Sheriff Election**: A special phase for electing a game moderator with extra voting power.
    *   **Complex Scenarios**: Handles tie-breakers, special death conditions (Hunter's last shot), and conflicting actions.
*   **AI-Powered Players**:
    *   Integrates with Large Language Models (LLMs) to create intelligent, human-like player agents.
    *   Each AI agent has a distinct "personality" and "memory," influencing its decisions.
    *   Supports dynamic prompt engineering for different languages (English and Chinese).
*   **Web-Based User Interface**:
    *   A real-time web UI allows human players to join games, interact, and observe AI agents.
    *   Features a dynamic game state display, role-based information filtering, and interactive controls.
*   **Comprehensive Logging**: Generates detailed, bilingual (EN/ZH) game logs for analysis and debugging.

## Project Architecture

The project is divided into several key modules:

-   **`game/`**: The core game engine.
    -   `game.py`: Manages the main game loop, player roster, and state transitions.
    -   `states.py`: Implements the state machine for all game phases (e.g., `NightState`, `DayState`, `VoteState`).
    -   `player.py`: Defines player objects, roles, and their attributes.
    -   `controllers.py`: Abstract base classes for player controllers (Human, AI, etc.).
    -   `history.py`: Manages the game's event log with visibility rules.

-   **`llm_player/`**: The AI agent implementation.
    -   `controller.py`: The `LLMController` class, which uses an LLM to make decisions based on game state and its persona.
    -   `prompts/`: Contains the prompt templates used to guide the LLM's reasoning for different actions and languages.

-   **`web/`**: The web interface.
    -   `server.py`: A FastAPI backend that serves the UI and handles communication between the frontend and the game engine.
    -   `static/`: Contains the HTML, CSS, and JavaScript for the client-side application.

-   **`simulation/`**: Tools for running automated, non-interactive simulations for testing and data collection.

## Getting Started

### Prerequisites

*   Python 3.9+
*   An OpenAI API Key (or other compatible LLM API key).

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up your API key:**
    Create a `.env` file in the root directory and add your API key:
    ```
    OPENAI_API_KEY="your-api-key-here"
    ```

### Running the Simulation

**1. Run a command-line simulation:**

This will run a game with only AI players.

```bash
python main.py
```

**2. Run the web interface:**

This allows a human player to join a game with AI opponents.

```bash
python main_web.py
```
Then, open your browser and navigate to `http://127.0.0.1:8000`.

## License

This project is licensed under the [MIT License](LICENSE).
