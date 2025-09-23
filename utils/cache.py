"""
Configuration caching utilities for the Guild Management Bot
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from database import GuildConfig, ConfigKV, get_session

logger = logging.getLogger(__name__)


class ConfigCache:
    """Handles caching of guild configurations."""
    
    def __init__(self):
        self._guild_configs: Dict[int, GuildConfig] = {}
        self._config_kvs: Dict[str, Any] = {}  # key format: "guild_id:key"
    
    async def get_guild_config(self, guild_id: int) -> Optional[GuildConfig]:
        """Get guild configuration with caching."""
        if guild_id not in self._guild_configs:
            async with get_session() as session:
                result = await session.execute(
                    select(GuildConfig).where(GuildConfig.guild_id == guild_id)
                )
                config = result.scalar_one_or_none()
                if config:
                    self._guild_configs[guild_id] = config
                return config
        
        return self._guild_configs[guild_id]
    
    async def update_guild_config(self, guild_id: int, **kwargs) -> GuildConfig:
        """Update guild configuration and invalidate cache."""
        async with get_session() as session:
            result = await session.execute(
                select(GuildConfig).where(GuildConfig.guild_id == guild_id)
            )
            config = result.scalar_one_or_none()
            
            if not config:
                config = GuildConfig(guild_id=guild_id, **kwargs)
                session.add(config)
            else:
                for key, value in kwargs.items():
                    setattr(config, key, value)
            
            await session.commit()
            await session.refresh(config)
            
            # Update cache
            self._guild_configs[guild_id] = config
            
            return config
    
    async def get_config_value(self, guild_id: int, key: str, default: Any = None) -> Any:
        """Get a configuration value with caching."""
        cache_key = f"{guild_id}:{key}"
        
        if cache_key not in self._config_kvs:
            async with get_session() as session:
                result = await session.execute(
                    select(ConfigKV).where(
                        ConfigKV.guild_id == guild_id,
                        ConfigKV.key == key
                    )
                )
                config_kv = result.scalar_one_or_none()
                
                if config_kv:
                    self._config_kvs[cache_key] = config_kv.value
                    return config_kv.value
                else:
                    self._config_kvs[cache_key] = default
                    return default
        
        return self._config_kvs[cache_key]
    
    async def set_config_value(self, guild_id: int, key: str, value: Any) -> None:
        """Set a configuration value and update cache."""
        async with get_session() as session:
            result = await session.execute(
                select(ConfigKV).where(
                    ConfigKV.guild_id == guild_id,
                    ConfigKV.key == key
                )
            )
            config_kv = result.scalar_one_or_none()
            
            if config_kv:
                config_kv.value = value
            else:
                config_kv = ConfigKV(guild_id=guild_id, key=key, value=value)
                session.add(config_kv)
            
            await session.commit()
            
            # Update cache
            cache_key = f"{guild_id}:{key}"
            self._config_kvs[cache_key] = value
    
    def invalidate_guild_config(self, guild_id: int) -> None:
        """Invalidate cached guild configuration."""
        if guild_id in self._guild_configs:
            del self._guild_configs[guild_id]
            logger.info(f"Invalidated guild config cache for guild {guild_id}")
    
    def invalidate_config_key(self, guild_id: int, key: str) -> None:
        """Invalidate a specific configuration key."""
        cache_key = f"{guild_id}:{key}"
        if cache_key in self._config_kvs:
            del self._config_kvs[cache_key]
            logger.info(f"Invalidated config cache for {cache_key}")
    
    def invalidate_guild_cache(self, guild_id: int) -> None:
        """Invalidate all cache entries for a guild."""
        # Remove guild config
        self.invalidate_guild_config(guild_id)
        
        # Remove all config KV entries for this guild
        keys_to_remove = [
            cache_key for cache_key in self._config_kvs.keys()
            if cache_key.startswith(f"{guild_id}:")
        ]
        
        for cache_key in keys_to_remove:
            del self._config_kvs[cache_key]
        
        logger.info(f"Invalidated all cache for guild {guild_id}")
    
    async def get_onboarding_config(self, guild_id: int) -> Dict[str, Any]:
        """Get onboarding configuration."""
        return await self.get_config_value(guild_id, "onboarding", {
            "enabled": True,
            "welcome_message": "Welcome! Please complete our onboarding process.",
            "completion_message": "Thank you for completing onboarding! Your application is under review."
        })
    
    async def get_poll_config(self, guild_id: int) -> Dict[str, Any]:
        """Get poll configuration."""
        return await self.get_config_value(guild_id, "polls.defaults", {
            "default_duration_hours": 24,
            "anonymous_default": False,
            "creator_roles": []
        })
    
    async def get_moderation_config(self, guild_id: int) -> Dict[str, Any]:
        """Get moderation configuration."""
        return await self.get_config_value(guild_id, "moderation", {
            "spam": {
                "enabled": False,
                "window_seconds": 10,
                "max_messages": 5,
                "max_mentions": 3,
                "action": "delete"
            },
            "swear": {
                "enabled": False,
                "delete_on_match": True,
                "action": "warn",
                "timeout_duration_minutes": 10
            },
            "watch_channels": [],
            "staff_roles": [],
            "swear_list": [],
            "allow_list": []
        })