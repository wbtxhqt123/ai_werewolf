# Web Interface Module

This directory contains the web-based user interface for the Werewolf game, allowing a human player to seamlessly interact with the AI-driven game engine.

## Architecture

The web module follows a modern client-server architecture:

*   **Backend**: A `FastAPI` server (`server.py`) that acts as the central hub. It serves the static frontend files and exposes a RESTful API for game interaction.
*   **Frontend**: A single-page application (`static/`) built with vanilla HTML, CSS, and JavaScript. It communicates with the backend to receive game state updates and send user actions.
*   **Controller**: A dedicated `WebController` (`controller.py`) that bridges the gap between the core game engine (`Game`) and the web server. It translates web requests into game actions and pushes game events to the frontend.

## Key Components

*   **`server.py`**: The FastAPI application. It manages game sessions and exposes the API endpoints that the frontend consumes.
*   **`controller.py`**: Implements the `WebController`, a crucial component that queues user input and retrieves game logs to be sent to the client.
*   **`static/`**: Contains all frontend assets.
    *   **`index.html`**: The main HTML file that defines the structure of the game interface.
    *   **`css/`**: Modular stylesheets organized by concerns (`base.css`, `layout.css`, `components.css`, `setup.css`, `game.css`, `modals.css`).
    *   **`js/app.js`**: The client-side JavaScript that handles all frontend logic: polling for game state, rendering updates, and sending user inputs back to the server.

## Frontend Features

*   **Interactive Lobby**: Players can configure the game by choosing their desired role, avatar, and the total number of players.
*   **Real-time Game View**:
    *   **Dynamic Atmosphere**: The UI background visually transitions between day and night to match the current game phase.
    *   **Player Status Circle**: All players are displayed in a circle, with clear visual cues for their status (alive, dead, sheriff).
    *   **Live Chat**: Game events and player speeches are displayed in a real-time chat log.
*   **Context-Aware Controls**: The interface presents the user with relevant action buttons (e.g., voting, using a special ability) only when their input is required.

## API Communication

The frontend and backend communicate via a set of RESTful API endpoints.

*   `POST /api/game/start`: Initializes a new game session with the specified configuration.
*   `GET /api/game/{game_id}/state`: Polls the server for the latest game state, including new logs and requests for user input.
*   `POST /api/game/{game_id}/action`: Submits a user's action (e.g., a vote, a speech) to the game engine.

## How to Run

1.  Ensure all project dependencies are installed (`pip install -r requirements.txt`).
2.  From the project's root directory, run the main web application entry point:
    ```bash
    python main_web.py
    ```
3.  Open your web browser and go to `http://127.0.0.1:8000` to start playing.
