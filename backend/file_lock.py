"""
Cross-platform file locking utility.

Supports:
- Unix/Linux/macOS: fcntl
- Windows: msvcrt

Usage:
    from file_lock import FileLock
    
    with FileLock("/path/to/file.json"):
        # Your code here - file is locked
        with open("/path/to/file.json", "w") as f:
            json.dump(data, f)
    # Lock automatically released
"""

import sys
import os


class FileLock:
    """
    Context manager for cross-platform exclusive file locking.
    
    Prevents race conditions when multiple processes access the same file.
    """
    
    def __init__(self, filepath: str):
        """
        Args:
            filepath: Path to the file to lock (a .lock file will be created)
        """
        self.filepath = filepath + ".lock"
        self.lock_file = None
    
    def __enter__(self):
        """Acquire exclusive lock"""
        # Create lock file if it doesn't exist
        if not os.path.exists(self.filepath):
            open(self.filepath, 'w').close()
        
        if sys.platform == "win32":
            # Windows: use msvcrt
            import msvcrt
            self.lock_file = open(self.filepath, "r+")
            # Lock 1 byte at position 0
            msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            # Unix/Linux/macOS: use fcntl
            import fcntl
            self.lock_file = open(self.filepath, "r+")
            # Acquire exclusive lock (blocks until available)
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock"""
        if self.lock_file:
            if sys.platform == "win32":
                import msvcrt
                # Unlock 1 byte at position 0
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                # Release lock
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            
            self.lock_file.close()
        
        # Return False to propagate exceptions
        return False


class SharedFileLock:
    """
    Context manager for shared (read) file locking.
    
    Multiple processes can hold shared locks simultaneously,
    but exclusive locks will block until all shared locks are released.
    
    Note: Only supported on Unix/Linux/macOS (not Windows).
    """
    
    def __init__(self, filepath: str):
        self.filepath = filepath + ".lock"
        self.lock_file = None
    
    def __enter__(self):
        """Acquire shared lock"""
        if sys.platform == "win32":
            # Windows doesn't support shared locks with msvcrt
            # Fall back to exclusive lock
            import msvcrt
            self.lock_file = open(self.filepath, "r+")
            msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            # Unix: use shared lock
            import fcntl
            if not os.path.exists(self.filepath):
                open(self.filepath, 'w').close()
            
            self.lock_file = open(self.filepath, "r+")
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_SH)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release lock"""
        if self.lock_file:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            
            self.lock_file.close()
        
        return False