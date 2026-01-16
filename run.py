"""
Entry point for hosting services that run Python files directly.
This adds the project root to sys.path so imports work correctly.
"""
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run the bot
from bot.main import main

if __name__ == "__main__":
    asyncio.run(main())
