"""
Redis Configuration for Task Queue System
Handles Redis connection settings and health checks
"""
import redis
from typing import Optional, Dict, Any
import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class RedisConfig:
    """Redis connection configuration and management"""
    
    def __init__(self, 
                 host: str = None, 
                 port: int = None, 
                 db: int = None,
                 password: str = None):
        # Default values with environment variable support
        # Use WSL2 IP for Windows development
        self.host = host or os.getenv("REDIS_HOST", "redis")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db or int(os.getenv("REDIS_DB", "0"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        
        self.connection_pool = None
        self._client = None
        
        logger.info(f"Redis configured: {self.host}:{self.port}/{self.db}")
    
    def get_redis_url(self) -> str:
        """Get Redis connection URL for Celery"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    def get_client(self) -> redis.Redis:
        """Get Redis client with connection pooling and fallback"""
        if self._client is None:
            if self.connection_pool is None:
                self.connection_pool = redis.ConnectionPool(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=True,
                    max_connections=20,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=False
                )
            self._client = redis.Redis(connection_pool=self.connection_pool)
        return self._client
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Redis connection health"""
        try:
            client = self.get_client()
            start_time = datetime.now()
            
            # Test basic connectivity
            client.ping()
            
            # Test read/write
            test_key = "health_check_test"
            client.set(test_key, "ok", ex=10)  # Expires in 10 seconds
            value = client.get(test_key)
            client.delete(test_key)
            
            response_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "response_time_ms": round(response_time * 1000, 2),
                "read_write_test": value == "ok",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"✅ Redis connection successful: {self.host}:{self.port}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return {
                "connected": False,
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis server statistics"""
        try:
            client = self.get_client()
            info = client.info()
            
            return {
                "connected": True,
                "server_info": {
                    "redis_version": info.get("redis_version"),
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "uptime_in_seconds": info.get("uptime_in_seconds"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses")
                },
                "database_info": {
                    f"db{self.db}": info.get(f"db{self.db}", "no keys")
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get Redis stats: {e}")
            return {
                "connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def clear_database(self) -> Dict[str, Any]:
        """Clear current Redis database (USE WITH CAUTION!)"""
        try:
            client = self.get_client()
            keys_before = len(client.keys("*"))
            client.flushdb()
            
            result = {
                "success": True,
                "keys_cleared": keys_before,
                "database": self.db,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.warning(f"⚠️ Redis database {self.db} cleared: {keys_before} keys removed")
            return result
            
        except Exception as e:
            logger.error(f"Failed to clear Redis database: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Global Redis configuration instance
redis_config = RedisConfig()

def get_redis_config() -> RedisConfig:
    """Get global Redis configuration instance"""
    return redis_config

def test_redis_connection() -> Dict[str, Any]:
    """Quick Redis connection test"""
    return redis_config.test_connection()

# Test connection on module import (for development)
if __name__ == "__main__":
    print("🔍 Testing Redis connection...")
    result = test_redis_connection()
    
    if result["connected"]:
        print(f"✅ Redis connected successfully!")
        print(f"   Host: {result['host']}:{result['port']}")
        print(f"   Response time: {result['response_time_ms']}ms")
    else:
        print(f"❌ Redis connection failed!")
        print(f"   Error: {result['error']}")