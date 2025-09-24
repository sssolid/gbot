"""
Moderation features for the Guild Management Bot - FIXED VERSION
"""
from typing import List

import discord
from sqlalchemy import select

from database import ModerationIncident, get_session


class ModerationCenterView(discord.ui.View):
    """Main moderation center interface."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(
        label="Spam Filter Settings",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🚫",
        row=0
    )
    async def spam_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open spam filter settings."""
        view = SpamFilterView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Swear Filter Settings", 
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🤬",
        row=0
    )
    async def swear_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open swear filter settings."""
        view = SwearFilterView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Watch Channels",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="👁️",
        row=1
    )
    async def watch_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure watched channels."""
        view = WatchChannelsView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Staff Exemptions",
        style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
        emoji="🛡️",
        row=1
    )
    async def staff_exemptions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure staff role exemptions."""
        view = StaffExemptionsView()
        await view.load_settings(interaction.guild_id, interaction.client)
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Recent Incidents",
        style=discord.ButtonStyle.primary, # type: ignore[arg-type]
        emoji="📋",
        row=2
    )
    async def recent_incidents(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View recent moderation incidents."""
        view = IncidentLogView()
        await view.show_incidents(interaction)


class SpamFilterView(discord.ui.View):
    """Spam filter configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.enabled = False
        self.window_seconds = 10
        self.max_messages = 5
        self.max_mentions = 3
        self.action = "delete"
    
    async def load_settings(self, guild_id: int, bot):
        """Load current spam filter settings."""
        if hasattr(bot, 'config_cache'):
            config = await bot.config_cache.get_moderation_config(guild_id)
            spam_config = config.get('spam', {})
            
            self.enabled = spam_config.get('enabled', False)
            self.window_seconds = spam_config.get('window_seconds', 10)
            self.max_messages = spam_config.get('max_messages', 5)
            self.max_mentions = spam_config.get('max_mentions', 3)
            self.action = spam_config.get('action', 'delete')
    
    async def save_settings(self, guild_id: int, bot):
        """Save spam filter settings."""
        if not hasattr(bot, 'config_cache'):
            return
        
        config_cache = bot.config_cache
        
        # Get current moderation config
        current_config = await config_cache.get_moderation_config(guild_id)
        
        # Update spam settings
        current_config['spam'] = {
            'enabled': self.enabled,
            'window_seconds': self.window_seconds,
            'max_messages': self.max_messages,
            'max_mentions': self.max_mentions,
            'action': self.action
        }
        
        # Save back to database
        await config_cache.set_config_value(guild_id, 'moderation', current_config)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display spam filter settings."""
        embed = discord.Embed(
            title="🚫 Spam Filter Settings",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Status",
            value="✅ Enabled" if self.enabled else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Time Window",
            value=f"{self.window_seconds} seconds",
            inline=True
        )
        
        embed.add_field(
            name="Max Messages",
            value=str(self.max_messages),
            inline=True
        )
        
        embed.add_field(
            name="Max Mentions",
            value=str(self.max_mentions),
            inline=True
        )
        
        embed.add_field(
            name="Action",
            value=self.action.title(),
            inline=True
        )
        
        # Clear all items and rebuild
        self.clear_items()
        
        # Enable/Disable toggle
        toggle_style = discord.ButtonStyle.success if not self.enabled else discord.ButtonStyle.danger
        toggle_label = "Enable" if not self.enabled else "Disable"
        toggle_button = discord.ui.Button(
            label=toggle_label,
            style=toggle_style, # type: ignore[arg-type]
            emoji="🔄"
        )
        toggle_button.callback = self.toggle_enabled
        self.add_item(toggle_button)
        
        if self.enabled:
            # Window seconds select
            window_select = discord.ui.Select(
                placeholder="Select time window...",
                options=[
                    discord.SelectOption(label="5 seconds", value="5"),
                    discord.SelectOption(label="10 seconds", value="10", default=self.window_seconds==10),
                    discord.SelectOption(label="15 seconds", value="15", default=self.window_seconds==15),
                    discord.SelectOption(label="30 seconds", value="30", default=self.window_seconds==30),
                    discord.SelectOption(label="60 seconds", value="60", default=self.window_seconds==60),
                ]
            )
            window_select.callback = self.set_window
            self.add_item(window_select)
            
            # Max messages select
            msg_select = discord.ui.Select(
                placeholder="Select max messages...",
                options=[
                    discord.SelectOption(label="3 messages", value="3", default=self.max_messages==3),
                    discord.SelectOption(label="5 messages", value="5", default=self.max_messages==5),
                    discord.SelectOption(label="7 messages", value="7", default=self.max_messages==7),
                    discord.SelectOption(label="10 messages", value="10", default=self.max_messages==10),
                ]
            )
            msg_select.callback = self.set_max_messages
            self.add_item(msg_select)
            
            # Action select
            action_select = discord.ui.Select(
                placeholder="Select action...",
                options=[
                    discord.SelectOption(label="Delete only", value="delete", default=self.action=="delete"),
                    discord.SelectOption(label="Warn user", value="warn", default=self.action=="warn"),
                    discord.SelectOption(label="Timeout user", value="timeout", default=self.action=="timeout"),
                ]
            )
            action_select.callback = self.set_action
            self.add_item(action_select)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save Settings",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="💾"
        )
        save_button.callback = self.save_settings_callback
        self.add_item(save_button)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def toggle_enabled(self, interaction: discord.Interaction):
        """Toggle spam filter enabled/disabled."""
        self.enabled = not self.enabled
        await self.show_settings(interaction)
    
    async def set_window(self, interaction: discord.Interaction):
        """Set time window."""
        self.window_seconds = int(interaction.data['values'][0])
        await self.show_settings(interaction)
    
    async def set_max_messages(self, interaction: discord.Interaction):
        """Set max messages."""
        self.max_messages = int(interaction.data['values'][0])
        await self.show_settings(interaction)
    
    async def set_action(self, interaction: discord.Interaction):
        """Set spam action."""
        self.action = interaction.data['values'][0]
        await self.show_settings(interaction)
    
    async def save_settings_callback(self, interaction: discord.Interaction):
        """Save settings callback."""
        bot = interaction.client
        await self.save_settings(interaction.guild_id, bot)
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Spam filter settings have been updated!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class SwearFilterView(discord.ui.View):
    """Swear filter configuration."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.enabled = False
        self.delete_on_match = True
        self.action = "warn"
        self.timeout_duration = 10
        self.swear_list = []
        self.allow_list = []
    
    async def load_settings(self, guild_id: int, bot):
        """Load swear filter settings."""
        if hasattr(bot, 'config_cache'):
            config = await bot.config_cache.get_moderation_config(guild_id)
            swear_config = config.get('swear', {})
            
            self.enabled = swear_config.get('enabled', False)
            self.delete_on_match = swear_config.get('delete_on_match', True)
            self.action = swear_config.get('action', 'warn')
            self.timeout_duration = swear_config.get('timeout_duration_minutes', 10)
            self.swear_list = config.get('swear_list', [])
            self.allow_list = config.get('allow_list', [])
    
    async def save_settings(self, guild_id: int, bot):
        """Save swear filter settings."""
        if not hasattr(bot, 'config_cache'):
            return
        
        config_cache = bot.config_cache
        
        # Get current moderation config
        current_config = await config_cache.get_moderation_config(guild_id)
        
        # Update swear settings
        current_config['swear'] = {
            'enabled': self.enabled,
            'delete_on_match': self.delete_on_match,
            'action': self.action,
            'timeout_duration_minutes': self.timeout_duration
        }
        current_config['swear_list'] = self.swear_list
        current_config['allow_list'] = self.allow_list
        
        # Save back to database
        await config_cache.set_config_value(guild_id, 'moderation', current_config)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display swear filter settings."""
        embed = discord.Embed(
            title="🤬 Swear Filter Settings",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Status",
            value="✅ Enabled" if self.enabled else "❌ Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Delete Messages",
            value="✅ Yes" if self.delete_on_match else "❌ No",
            inline=True
        )
        
        embed.add_field(
            name="Action",
            value=self.action.title(),
            inline=True
        )
        
        if self.action == "timeout":
            embed.add_field(
                name="Timeout Duration",
                value=f"{self.timeout_duration} minutes",
                inline=True
            )
        
        embed.add_field(
            name="Blocked Words",
            value=f"{len(self.swear_list)} terms" if self.swear_list else "None",
            inline=True
        )
        
        embed.add_field(
            name="Allowed Words",
            value=f"{len(self.allow_list)} terms" if self.allow_list else "None",
            inline=True
        )
        
        # Clear and rebuild view
        self.clear_items()
        
        # Enable/Disable toggle
        toggle_style = discord.ButtonStyle.success if not self.enabled else discord.ButtonStyle.danger
        toggle_label = "Enable" if not self.enabled else "Disable"
        toggle_button = discord.ui.Button(
            label=toggle_label,
            style=toggle_style, # type: ignore[arg-type]
            emoji="🔄"
        )
        toggle_button.callback = self.toggle_enabled
        self.add_item(toggle_button)
        
        if self.enabled:
            # Delete messages toggle
            delete_toggle = discord.ui.Button(
                label=f"Delete: {'ON' if self.delete_on_match else 'OFF'}",
                style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
                emoji="🗑️"
            )
            delete_toggle.callback = self.toggle_delete
            self.add_item(delete_toggle)
            
            # Action select
            action_select = discord.ui.Select(
                placeholder="Select action...",
                options=[
                    discord.SelectOption(label="Warn user", value="warn", default=self.action=="warn"),
                    discord.SelectOption(label="Timeout user", value="timeout", default=self.action=="timeout"),
                    discord.SelectOption(label="Delete only", value="delete", default=self.action=="delete"),
                ]
            )
            action_select.callback = self.set_action
            self.add_item(action_select)
            
            # Manage word lists
            manage_swear_button = discord.ui.Button(
                label="Manage Blocked Words",
                style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
                emoji="📝"
            )
            manage_swear_button.callback = self.manage_swear_list
            self.add_item(manage_swear_button)
            
            manage_allow_button = discord.ui.Button(
                label="Manage Allowed Words",
                style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
                emoji="✅"
            )
            manage_allow_button.callback = self.manage_allow_list
            self.add_item(manage_allow_button)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save Settings",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="💾"
        )
        save_button.callback = self.save_settings_callback
        self.add_item(save_button)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def toggle_enabled(self, interaction: discord.Interaction):
        """Toggle swear filter enabled/disabled."""
        self.enabled = not self.enabled
        await self.show_settings(interaction)
    
    async def toggle_delete(self, interaction: discord.Interaction):
        """Toggle delete on match."""
        self.delete_on_match = not self.delete_on_match
        await self.show_settings(interaction)
    
    async def set_action(self, interaction: discord.Interaction):
        """Set swear filter action."""
        self.action = interaction.data['values'][0]
        await self.show_settings(interaction)
    
    async def manage_swear_list(self, interaction: discord.Interaction):
        """Open swear list management."""
        view = WordListManagementView(self.swear_list, "Blocked Words", self)
        await view.show_list(interaction)
    
    async def manage_allow_list(self, interaction: discord.Interaction):
        """Open allow list management."""
        view = WordListManagementView(self.allow_list, "Allowed Words", self)
        await view.show_list(interaction)
    
    async def save_settings_callback(self, interaction: discord.Interaction):
        """Save settings callback."""
        bot = interaction.client
        await self.save_settings(interaction.guild_id, bot)
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Swear filter settings have been updated!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class WordListManagementView(discord.ui.View):
    """View for managing word lists."""
    
    def __init__(self, term_list: List[str], list_title: str, parent_view):
        super().__init__(timeout=300)
        self.term_list = term_list
        self.list_title = list_title
        self.parent_view = parent_view
        self.current_page = 0
    
    async def show_list(self, interaction: discord.Interaction):
        """Show the word list management interface."""
        embed = discord.Embed(
            title=f"📝 {self.list_title}",
            color=discord.Color.blue()
        )
        
        if not self.term_list:
            embed.add_field(
                name="No Terms",
                value="No terms have been added yet.",
                inline=False
            )
        else:
            per_page = 10
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_terms = self.term_list[start_idx:end_idx]
            
            embed.add_field(
                name=f"Terms (Page {self.current_page + 1})",
                value="\n".join([f"{start_idx + i + 1}. `{term}`" for i, term in enumerate(page_terms)]) or "No terms",
                inline=False
            )
        
        # Clear and rebuild view
        self.clear_items()
        
        # Navigation buttons
        if len(self.term_list) > 10:
            if self.current_page > 0:
                prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary) # type: ignore[arg-type]
                prev_button.callback = self.previous_page
                self.add_item(prev_button)
            
            if (self.current_page + 1) * 10 < len(self.term_list):
                next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary) # type: ignore[arg-type]
                next_button.callback = self.next_page
                self.add_item(next_button)
        
        # Management buttons
        add_button = discord.ui.Button(
            label="Add Term",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="➕"
        )
        add_button.callback = self.add_term
        self.add_item(add_button)
        
        if self.term_list:
            remove_button = discord.ui.Button(
                label="Remove Term",
                style=discord.ButtonStyle.danger, # type: ignore[arg-type]
                emoji="➖"
            )
            remove_button.callback = self.remove_term
            self.add_item(remove_button)
        
        # Back button
        back_button = discord.ui.Button(
            label="Back",
            style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
            emoji="🔙"
        )
        back_button.callback = self.back_to_parent
        self.add_item(back_button)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    async def add_term(self, interaction: discord.Interaction):
        """Add a term to the list."""
        modal = AddTermModal(self)
        await interaction.response.send_modal(modal)
    
    async def remove_term(self, interaction: discord.Interaction):
        """Remove a term from the list."""
        if not self.term_list:
            return
        
        view = RemoveTermView(self)
        await view.show_remove_options(interaction)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_list(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.term_list) - 1) // 10
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_list(interaction)
    
    async def back_to_parent(self, interaction: discord.Interaction):
        """Return to parent view."""
        await self.parent_view.show_settings(interaction)


class AddTermModal(discord.ui.Modal):
    """Modal for adding terms to word lists."""
    
    def __init__(self, word_list_view: WordListManagementView):
        super().__init__(title=f"Add to {word_list_view.list_title}")
        self.word_list_view = word_list_view
        
        self.term_input = discord.ui.TextInput(
            label="Term",
            placeholder="Enter a word or phrase (use * for wildcards)",
            required=True,
            max_length=100
        )
        self.add_item(self.term_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle term addition."""
        term = self.term_input.value.strip().lower()
        
        if not term:
            embed = discord.Embed(
                title="❌ Invalid Term",
                description="Please enter a valid term.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if term in self.word_list_view.term_list:
            embed = discord.Embed(
                title="❌ Duplicate Term",
                description=f"`{term}` is already in the {self.word_list_view.list_title.lower()}.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        self.word_list_view.term_list.append(term)
        
        embed = discord.Embed(
            title="✅ Term Added",
            description=f"Added `{term}` to {self.word_list_view.list_title.lower()}.",
            color=discord.Color.green()
        )
        
        if '*' in term:
            embed.add_field(
                name="Wildcard Note",
                value="This term uses wildcards and will match partial words.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RemoveTermView(discord.ui.View):
    """View for removing terms from word lists."""
    
    def __init__(self, word_list_view: WordListManagementView):
        super().__init__(timeout=300)
        self.word_list_view = word_list_view
    
    async def show_remove_options(self, interaction: discord.Interaction):
        """Show term removal options."""
        embed = discord.Embed(
            title=f"Remove from {self.word_list_view.list_title}",
            description="Select a term to remove:",
            color=discord.Color.orange()
        )
        
        # Create select menu with terms
        options = []
        for i, term in enumerate(self.word_list_view.term_list[:25]):  # Discord limit
            options.append(discord.SelectOption(
                label=term[:100],  # Discord limit
                value=str(i),
                description=f"Remove '{term}'"
            ))
        
        if not options:
            embed.description = "No terms to remove."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        select = discord.ui.Select(
            placeholder="Choose a term to remove...",
            options=options
        )
        select.callback = self.remove_selected_term
        self.clear_items()
        self.add_item(select)
        
        # Cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary # type: ignore[arg-type]
        )
        cancel_button.callback = self.cancel_removal
        self.add_item(cancel_button)
        
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
    
    async def remove_selected_term(self, interaction: discord.Interaction):
        """Remove the selected term."""
        selected_index = int(interaction.data['values'][0])
        removed_term = self.word_list_view.term_list.pop(selected_index)
        
        embed = discord.Embed(
            title="✅ Term Removed",
            description=f"Removed `{removed_term}` from {self.word_list_view.list_title.lower()}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def cancel_removal(self, interaction: discord.Interaction):
        """Cancel term removal."""
        await self.word_list_view.show_list(interaction)


class WatchChannelsView(discord.ui.View):
    """Configure watched channels for moderation."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.watch_channels = []
    
    async def load_settings(self, guild_id: int, bot):
        """Load watch channels settings."""
        if hasattr(bot, 'config_cache'):
            config = await bot.config_cache.get_moderation_config(guild_id)
            self.watch_channels = config.get('watch_channels', [])
    
    async def save_settings(self, guild_id: int, bot):
        """Save watch channels settings."""
        if not hasattr(bot, 'config_cache'):
            return
        
        config_cache = bot.config_cache
        
        # Get current moderation config
        current_config = await config_cache.get_moderation_config(guild_id)
        
        # Update watch channels
        current_config['watch_channels'] = self.watch_channels
        
        # Save back to database
        await config_cache.set_config_value(guild_id, 'moderation', current_config)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display watch channels settings."""
        embed = discord.Embed(
            title="👁️ Watch Channels",
            description="Configure which channels are monitored by the moderation filters.",
            color=discord.Color.blue()
        )
        
        if not self.watch_channels:
            embed.add_field(
                name="Watched Channels",
                value="All channels (no specific channels selected)",
                inline=False
            )
        else:
            channel_mentions = []
            for channel_id in self.watch_channels:
                channel = interaction.guild.get_channel(int(channel_id))
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"<#{channel_id}> (deleted)")
            
            embed.add_field(
                name="Watched Channels",
                value="\n".join(channel_mentions) if channel_mentions else "None",
                inline=False
            )
        
        embed.add_field(
            name="Note",
            value="If no channels are selected, moderation will apply to all channels.",
            inline=False
        )
        
        # Clear and rebuild view
        self.clear_items()
        
        # Add channel button
        add_channel_button = discord.ui.Button(
            label="Add Channel",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="➕"
        )
        add_channel_button.callback = self.add_channel
        self.add_item(add_channel_button)
        
        # Remove channel button
        if self.watch_channels:
            remove_channel_button = discord.ui.Button(
                label="Remove Channel",
                style=discord.ButtonStyle.danger, # type: ignore[arg-type]
                emoji="➖"
            )
            remove_channel_button.callback = self.remove_channel
            self.add_item(remove_channel_button)
        
        # Clear all button
        if self.watch_channels:
            clear_button = discord.ui.Button(
                label="Clear All",
                style=discord.ButtonStyle.secondary, # type: ignore[arg-type]
                emoji="🗑️"
            )
            clear_button.callback = self.clear_all_channels
            self.add_item(clear_button)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save Settings",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="💾"
        )
        save_button.callback = self.save_settings_callback
        self.add_item(save_button)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def add_channel(self, interaction: discord.Interaction):
        """Add a channel to watch list."""
        # Get text channels from the guild
        text_channels = [ch for ch in interaction.guild.channels 
                        if isinstance(ch, discord.TextChannel) and str(ch.id) not in self.watch_channels]
        
        if not text_channels:
            embed = discord.Embed(
                title="❌ No Channels Available",
                description="No text channels available to add.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create select menu with channels
        options = []
        for channel in text_channels[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=f"#{channel.name}",
                value=str(channel.id),
                description=f"Add {channel.name} to watch list"
            ))
        
        select = discord.ui.Select(
            placeholder="Choose a channel to add...",
            options=options
        )
        select.callback = self.add_selected_channel
        
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        
        embed = discord.Embed(
            title="Add Watch Channel",
            description="Select a channel to add to the watch list:",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def add_selected_channel(self, interaction: discord.Interaction):
        """Add the selected channel."""
        channel_id = interaction.data['values'][0]
        channel = interaction.guild.get_channel(int(channel_id))
        
        if channel_id not in self.watch_channels:
            self.watch_channels.append(channel_id)
        
        embed = discord.Embed(
            title="✅ Channel Added",
            description=f"Added {channel.mention} to watch list.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def remove_channel(self, interaction: discord.Interaction):
        """Remove a channel from watch list."""
        if not self.watch_channels:
            return
        
        # Create select menu with watched channels
        options = []
        for channel_id in self.watch_channels:
            channel = interaction.guild.get_channel(int(channel_id))
            channel_name = channel.name if channel else f"Deleted Channel ({channel_id})"
            options.append(discord.SelectOption(
                label=f"#{channel_name}",
                value=channel_id,
                description=f"Remove {channel_name} from watch list"
            ))
        
        select = discord.ui.Select(
            placeholder="Choose a channel to remove...",
            options=options
        )
        select.callback = self.remove_selected_channel
        
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        
        embed = discord.Embed(
            title="Remove Watch Channel",
            description="Select a channel to remove from the watch list:",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def remove_selected_channel(self, interaction: discord.Interaction):
        """Remove the selected channel."""
        channel_id = interaction.data['values'][0]
        channel = interaction.guild.get_channel(int(channel_id))
        
        if channel_id in self.watch_channels:
            self.watch_channels.remove(channel_id)
        
        channel_name = channel.mention if channel else f"Channel {channel_id}"
        
        embed = discord.Embed(
            title="✅ Channel Removed",
            description=f"Removed {channel_name} from watch list.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def clear_all_channels(self, interaction: discord.Interaction):
        """Clear all watched channels."""
        self.watch_channels.clear()
        
        embed = discord.Embed(
            title="✅ All Channels Cleared",
            description="Cleared all channels from watch list. Moderation will now apply to all channels.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def save_settings_callback(self, interaction: discord.Interaction):
        """Save settings callback."""
        bot = interaction.client
        await self.save_settings(interaction.guild_id, bot)
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Watch channels settings have been updated!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class StaffExemptionsView(discord.ui.View):
    """Configure staff role exemptions."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.staff_roles = []
    
    async def load_settings(self, guild_id: int, bot):
        """Load staff exemption settings."""
        if hasattr(bot, 'config_cache'):
            config = await bot.config_cache.get_moderation_config(guild_id)
            self.staff_roles = config.get('staff_roles', [])
    
    async def save_settings(self, guild_id: int, bot):
        """Save staff exemption settings."""
        if not hasattr(bot, 'config_cache'):
            return
        
        config_cache = bot.config_cache
        
        # Get current moderation config
        current_config = await config_cache.get_moderation_config(guild_id)
        
        # Update staff roles
        current_config['staff_roles'] = self.staff_roles
        
        # Save back to database
        await config_cache.set_config_value(guild_id, 'moderation', current_config)
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display staff exemptions."""
        embed = discord.Embed(
            title="🛡️ Staff Exemptions",
            description="Configure which roles are exempt from moderation filters.",
            color=discord.Color.gold()
        )
        
        if not self.staff_roles:
            embed.add_field(
                name="Exempt Roles",
                value="No roles are currently exempt from moderation.",
                inline=False
            )
        else:
            role_mentions = []
            for role_id in self.staff_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(f"<@&{role_id}> (deleted)")
            
            embed.add_field(
                name="Exempt Roles",
                value="\n".join(role_mentions) if role_mentions else "None",
                inline=False
            )
        
        embed.add_field(
            name="Note",
            value="Members with these roles will not be affected by spam or swear filters.",
            inline=False
        )
        
        # Clear and rebuild view
        self.clear_items()
        
        # Add role button
        add_role_button = discord.ui.Button(
            label="Add Role",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="➕"
        )
        add_role_button.callback = self.add_role
        self.add_item(add_role_button)
        
        # Remove role button
        if self.staff_roles:
            remove_role_button = discord.ui.Button(
                label="Remove Role",
                style=discord.ButtonStyle.danger, # type: ignore[arg-type]
                emoji="➖"
            )
            remove_role_button.callback = self.remove_role
            self.add_item(remove_role_button)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save Settings",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="💾"
        )
        save_button.callback = self.save_settings_callback
        self.add_item(save_button)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def add_role(self, interaction: discord.Interaction):
        """Add a role to exemption list."""
        # Get roles that aren't already exempt
        available_roles = [role for role in interaction.guild.roles 
                         if str(role.id) not in self.staff_roles and role != interaction.guild.default_role]
        
        if not available_roles:
            embed = discord.Embed(
                title="❌ No Roles Available",
                description="No roles available to add to exemptions.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create select menu with roles
        options = []
        for role in available_roles[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=role.name,
                value=str(role.id),
                description=f"Add {role.name} to exemptions"
            ))
        
        select = discord.ui.Select(
            placeholder="Choose a role to add...",
            options=options
        )
        select.callback = self.add_selected_role
        
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        
        embed = discord.Embed(
            title="Add Staff Exemption",
            description="Select a role to exempt from moderation:",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def add_selected_role(self, interaction: discord.Interaction):
        """Add the selected role."""
        role_id = interaction.data['values'][0]
        role = interaction.guild.get_role(int(role_id))
        
        if role_id not in self.staff_roles:
            self.staff_roles.append(role_id)
        
        embed = discord.Embed(
            title="✅ Role Added",
            description=f"Added {role.mention} to staff exemptions.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def remove_role(self, interaction: discord.Interaction):
        """Remove a role from exemption list."""
        if not self.staff_roles:
            return
        
        # Create select menu with exempt roles
        options = []
        for role_id in self.staff_roles:
            role = interaction.guild.get_role(int(role_id))
            role_name = role.name if role else f"Deleted Role ({role_id})"
            options.append(discord.SelectOption(
                label=role_name,
                value=role_id,
                description=f"Remove {role_name} from exemptions"
            ))
        
        select = discord.ui.Select(
            placeholder="Choose a role to remove...",
            options=options
        )
        select.callback = self.remove_selected_role
        
        view = discord.ui.View(timeout=300)
        view.add_item(select)
        
        embed = discord.Embed(
            title="Remove Staff Exemption",
            description="Select a role to remove from exemptions:",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def remove_selected_role(self, interaction: discord.Interaction):
        """Remove the selected role."""
        role_id = interaction.data['values'][0]
        role = interaction.guild.get_role(int(role_id))
        
        if role_id in self.staff_roles:
            self.staff_roles.remove(role_id)
        
        role_name = role.mention if role else f"Role {role_id}"
        
        embed = discord.Embed(
            title="✅ Role Removed",
            description=f"Removed {role_name} from staff exemptions.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def save_settings_callback(self, interaction: discord.Interaction):
        """Save settings callback."""
        bot = interaction.client
        await self.save_settings(interaction.guild_id, bot)
        
        embed = discord.Embed(
            title="✅ Settings Saved",
            description="Staff exemption settings have been updated!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class IncidentLogView(discord.ui.View):
    """View recent moderation incidents."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.incidents: List[ModerationIncident] = []
    
    async def show_incidents(self, interaction: discord.Interaction):
        """Show recent moderation incidents."""
        # Load recent incidents
        async with get_session() as session:
            result = await session.execute(
                select(ModerationIncident)
                .where(ModerationIncident.guild_id == interaction.guild_id)
                .order_by(ModerationIncident.created_at.desc())
                .limit(50)
            )
            self.incidents = result.scalars().all()
        
        if not self.incidents:
            embed = discord.Embed(
                title="📋 Recent Incidents",
                description="No moderation incidents recorded.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Pagination
        per_page = 5
        start_idx = self.current_page * per_page
        end_idx = start_idx + per_page
        page_incidents = self.incidents[start_idx:end_idx]
        
        embed = discord.Embed(
            title="📋 Recent Incidents",
            description=f"Page {self.current_page + 1} of {(len(self.incidents) - 1) // per_page + 1}",
            color=discord.Color.orange()
        )
        
        for incident in page_incidents:
            user = interaction.guild.get_member(incident.user_id)
            user_name = user.display_name if user else f"User {incident.user_id}"
            
            channel = interaction.guild.get_channel(incident.channel_id)
            channel_name = channel.mention if channel else f"#{incident.channel_id}"
            
            embed.add_field(
                name=f"🚨 {incident.type.title()} - {user_name}",
                value=(
                    f"**Channel:** {channel_name}\n"
                    f"**Action:** {incident.action_taken or 'None'}\n"
                    f"**Reason:** {incident.reason or 'No reason provided'}\n"
                    f"**Time:** {discord.utils.format_dt(incident.created_at, 'R')}"
                ),
                inline=False
            )
        
        # Clear and rebuild view
        self.clear_items()
        
        # Navigation buttons
        if len(self.incidents) > per_page:
            if self.current_page > 0:
                prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary) # type: ignore[arg-type]
                prev_button.callback = self.previous_page
                self.add_item(prev_button)
            
            if (self.current_page + 1) * per_page < len(self.incidents):
                next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary) # type: ignore[arg-type]
                next_button.callback = self.next_page
                self.add_item(next_button)
        
        # Refresh button
        refresh_button = discord.ui.Button(
            label="Refresh",
            style=discord.ButtonStyle.primary, # type: ignore[arg-type]
            emoji="🔄"
        )
        refresh_button.callback = self.refresh_incidents
        self.add_item(refresh_button)
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_incidents(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.incidents) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_incidents(interaction)
    
    async def refresh_incidents(self, interaction: discord.Interaction):
        """Refresh the incidents list."""
        self.current_page = 0
        await self.show_incidents(interaction)