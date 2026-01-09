"""
Cross-platform signal handling utility
=======================================
Provides Windows-compatible signal handling for asyncio applications.
"""

import asyncio
import signal
import platform
from typing import Callable, Optional


def setup_signal_handlers(shutdown_callback: Optional[Callable] = None) -> asyncio.Event:
    """
    Set up cross-platform signal handlers for graceful shutdown.
    
    Args:
        shutdown_callback: Optional callback function to call on shutdown signal
        
    Returns:
        asyncio.Event that will be set when shutdown signal is received
    """
    shutdown_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig=None, frame=None):
        """Signal handler for graceful shutdown"""
        if shutdown_callback:
            shutdown_callback()
        shutdown_event.set()
    
    # Signal handling - Windows doesn't support add_signal_handler
    if platform.system() == 'Windows':
        # Windows-compatible signal handling
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    else:
        # Unix/Linux signal handling
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                # Fallback for systems that don't support add_signal_handler
                signal.signal(sig, signal_handler)
    
    return shutdown_event

