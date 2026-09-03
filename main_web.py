import uvicorn
from web.server import app

def main():
    """
    The main entry point for the web-based Werewolf game.
    """
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()