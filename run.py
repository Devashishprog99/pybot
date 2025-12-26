import os
import threading
import signal
import sys
from dashboard import app
from bot import create_bot_application
from telegram import Update
import logging
import asyncio

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_flask():
    """Run Flask application"""
    port = int(os.environ.get('PORT', 5000))
    # Use threaded=True for handling concurrent requests
    app.run(host='0.0.0.0', port=port, threaded=True)

def main():
    """Run both Bot and Web Dashboard"""
    
    # 1. Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Web Dashboard started in background thread")
    
    # 2. Start Bot in main thread (required for proper signal handling)
    try:
        bot_app = create_bot_application()
        logger.info("Bot application created")
        
        # Run polling (this is blocking)
        logger.info("Starting bot polling...")
        bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        # If bot fails, we should exit so Railway restarts the container
        sys.exit(1)

if __name__ == "__main__":
    main()
