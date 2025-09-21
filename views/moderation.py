"""
Moderation features for the Guild Management Bot
"""
import discord
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import re

from database import ModerationIncident, get_session
from utils.permissions import PermissionChecker, require_moderator, require_admin


class ModerationCenterView(discord.ui.View):
    """Main moderation center interface."""
    
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(
        label="Spam Filter Settings",
        style=discord.ButtonStyle.secondary,
        emoji="🚫",
        row=0
    )
    async def spam_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open spam filter settings."""
        view = SpamFilterView()
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Swear Filter Settings", 
        style=discord.ButtonStyle.secondary,
        emoji="🤬",
        row=0
    )
    async def swear_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open swear filter settings."""
        view = SwearFilterView()
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Watch Channels",
        style=discord.ButtonStyle.secondary,
        emoji="👁️",
        row=1
    )
    async def watch_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure watched channels."""
        view = WatchChannelsView()
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Staff Exemptions",
        style=discord.ButtonStyle.secondary,
        emoji="🛡️",
        row=1
    )
    async def staff_exemptions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Configure staff role exemptions."""
        view = StaffExemptionsView()
        await view.show_settings(interaction)
    
    @discord.ui.button(
        label="Recent Incidents",
        style=discord.ButtonStyle.primary,
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
    
    async def load_settings(self, guild_id: int):
        """Load current spam filter settings."""
        bot = None
        # Try to get bot instance from interaction context
        # This is a simplified approach - in practice you'd want better bot access
        try:
            # Get settings from cache if available
            config = await self.get_moderation_config(guild_id)
            spam_config = config.get("spam", {})
            
            self.enabled = spam_config.get("enabled", False)
            self.window_seconds = spam_config.get("window_seconds", 10)
            self.max_messages = spam_config.get("max_messages", 5)
            self.max_mentions = spam_config.get("max_mentions", 3)
            self.action = spam_config.get("action", "delete")
        except:
            pass  # Use defaults
    
    async def save_settings(self, guild_id: int):
        """Save spam filter settings."""
        # This would typically use the bot's config cache
        # Simplified for this example
        pass
    
    async def get_moderation_config(self, guild_id: int) -> Dict[str, Any]:
        """Get moderation config - simplified."""
        return {
            "spam": {
                "enabled": self.enabled,
                "window_seconds": self.window_seconds,
                "max_messages": self.max_messages,
                "max_mentions": self.max_mentions,
                "action": self.action
            }
        }
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display spam filter settings."""
        await self.load_settings(interaction.guild_id)
        
        embed = discord.Embed(
            title="🚫 Spam Filter Settings",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Status",
            value="🟢 Enabled" if self.enabled else "🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Time Window",
            value=f"{self.window_seconds} seconds",
            inline=True
        )
        
        embed.add_field(
            name="Max Messages",
            value=f"{self.max_messages} messages",
            inline=True
        )
        
        embed.add_field(
            name="Max Mentions",
            value=f"{self.max_mentions} mentions",
            inline=True
        )
        
        embed.add_field(
            name="Action",
            value=self.action.title(),
            inline=True
        )
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Enable/Disable toggle
        toggle_button = discord.ui.Button(
            label=f"{'Disable' if self.enabled else 'Enable'} Filter",
            style=discord.ButtonStyle.danger if self.enabled else discord.ButtonStyle.success,
            emoji="🔴" if self.enabled else "🟢"
        )
        toggle_button.callback = self.toggle_enabled
        self.add_item(toggle_button)
        
        # Window time selector
        window_select = discord.ui.Select(
            placeholder=f"Time Window: {self.window_seconds}s",
            options=[
                discord.SelectOption(label="5 seconds", value="5"),
                discord.SelectOption(label="10 seconds", value="10", default=self.window_seconds==10),
                discord.SelectOption(label="15 seconds", value="15", default=self.window_seconds==15),
                discord.SelectOption(label="30 seconds", value="30", default=self.window_seconds==30),
                discord.SelectOption(label="60 seconds", value="60", default=self.window_seconds==60)
            ]
        )
        window_select.callback = self.set_window
        self.add_item(window_select)
        
        # Max messages selector
        msg_select = discord.ui.Select(
            placeholder=f"Max Messages: {self.max_messages}",
            options=[
                discord.SelectOption(label="3 messages", value="3"),
                discord.SelectOption(label="5 messages", value="5", default=self.max_messages==5),
                discord.SelectOption(label="8 messages", value="8", default=self.max_messages==8),
                discord.SelectOption(label="10 messages", value="10", default=self.max_messages==10),
                discord.SelectOption(label="15 messages", value="15", default=self.max_messages==15)
            ]
        )
        msg_select.callback = self.set_max_messages
        self.add_item(msg_select)
        
        # Action selector
        action_select = discord.ui.Select(
            placeholder=f"Action: {self.action.title()}",
            options=[
                discord.SelectOption(label="Delete Only", value="delete", default=self.action=="delete"),
                discord.SelectOption(label="Warn User", value="warn", default=self.action=="warn"),
                discord.SelectOption(label="Timeout User", value="timeout", default=self.action=="timeout")
            ]
        )
        action_select.callback = self.set_action
        self.add_item(action_select)
        
        # Save button
        save_button = discord.ui.Button(
            label="Save Settings",
            style=discord.ButtonStyle.primary,
            emoji="💾"
        )
        save_button.callback = self.save_settings_callback
        self.add_item(save_button)
    
    async def toggle_enabled(self, interaction: discord.Interaction):
        """Toggle spam filter enabled status."""
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
        await self.save_settings(interaction.guild_id)
        
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
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display swear filter settings."""
        # Load settings here
        
        embed = discord.Embed(
            title="🤬 Swear Filter Settings",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Status",
            value="🟢 Enabled" if self.enabled else "🔴 Disabled",
            inline=True
        )
        
        embed.add_field(
            name="Delete Messages",
            value="Yes" if self.delete_on_match else "No",
            inline=True
        )
        
        embed.add_field(
            name="Action",
            value=self.action.title(),
            inline=True
        )
        
        embed.add_field(
            name="Blocked Terms",
            value=f"{len(self.swear_list)} terms",
            inline=True
        )
        
        embed.add_field(
            name="Allowed Terms",
            value=f"{len(self.allow_list)} terms",
            inline=True
        )
        
        if self.action == "timeout":
            embed.add_field(
                name="Timeout Duration",
                value=f"{self.timeout_duration} minutes",
                inline=True
            )
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Enable/Disable
        toggle_button = discord.ui.Button(
            label=f"{'Disable' if self.enabled else 'Enable'} Filter",
            style=discord.ButtonStyle.danger if self.enabled else discord.ButtonStyle.success
        )
        toggle_button.callback = self.toggle_enabled
        self.add_item(toggle_button)
        
        # Delete toggle
        delete_button = discord.ui.Button(
            label=f"Delete Messages: {'ON' if self.delete_on_match else 'OFF'}",
            style=discord.ButtonStyle.success if self.delete_on_match else discord.ButtonStyle.secondary
        )
        delete_button.callback = self.toggle_delete
        self.add_item(delete_button)
        
        # Manage swear list
        swear_button = discord.ui.Button(
            label="Manage Blocked Terms",
            style=discord.ButtonStyle.secondary,
            emoji="📝"
        )
        swear_button.callback = self.manage_swear_list
        self.add_item(swear_button)
        
        # Manage allow list
        allow_button = discord.ui.Button(
            label="Manage Allowed Terms",
            style=discord.ButtonStyle.secondary,
            emoji="✅"
        )
        allow_button.callback = self.manage_allow_list
        self.add_item(allow_button)
    
    async def toggle_enabled(self, interaction: discord.Interaction):
        """Toggle swear filter."""
        self.enabled = not self.enabled
        await self.show_settings(interaction)
    
    async def toggle_delete(self, interaction: discord.Interaction):
        """Toggle delete on match."""
        self.delete_on_match = not self.delete_on_match
        await self.show_settings(interaction)
    
    async def manage_swear_list(self, interaction: discord.Interaction):
        """Manage swear list."""
        view = TermListManagerView(self.swear_list, "Blocked Terms", is_swear_list=True)
        await view.show_list(interaction)
    
    async def manage_allow_list(self, interaction: discord.Interaction):
        """Manage allow list."""
        view = TermListManagerView(self.allow_list, "Allowed Terms", is_swear_list=False)
        await view.show_list(interaction)


class TermListManagerView(discord.ui.View):
    """Manage swear/allow lists."""
    
    def __init__(self, term_list: List[str], title: str, is_swear_list: bool = True):
        super().__init__(timeout=300)
        self.term_list = term_list
        self.title = title
        self.is_swear_list = is_swear_list
        self.current_page = 0
    
    async def show_list(self, interaction: discord.Interaction):
        """Display the term list."""
        embed = discord.Embed(
            title=f"📝 {self.title}",
            color=discord.Color.red() if self.is_swear_list else discord.Color.green()
        )
        
        if not self.term_list:
            embed.description = f"No {self.title.lower()} configured."
        else:
            # Pagination
            per_page = 10
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_terms = self.term_list[start_idx:end_idx]
            
            embed.description = "\n".join(f"{start_idx + i + 1}. `{term}`" for i, term in enumerate(page_terms))
            
            if len(self.term_list) > per_page:
                embed.set_footer(text=f"Page {self.current_page + 1} of {(len(self.term_list) - 1) // per_page + 1}")
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Add term button
        add_button = discord.ui.Button(
            label="Add Term",
            style=discord.ButtonStyle.primary,
            emoji="➕"
        )
        add_button.callback = self.add_term
        self.add_item(add_button)
        
        if self.term_list:
            # Remove term dropdown
            if len(self.term_list) <= 25:  # Discord limit
                options = [
                    discord.SelectOption(label=term[:100], value=str(i))
                    for i, term in enumerate(self.term_list)
                ]
                
                remove_select = discord.ui.Select(
                    placeholder="Select term to remove...",
                    options=options
                )
                remove_select.callback = self.remove_term
                self.add_item(remove_select)
        
        # Pagination buttons
        per_page = 10
        if self.current_page > 0:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if (self.current_page + 1) * per_page < len(self.term_list):
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
    
    async def add_term(self, interaction: discord.Interaction):
        """Add a new term."""
        modal = AddTermModal(self.term_list, self.title)
        await interaction.response.send_modal(modal)
    
    async def remove_term(self, interaction: discord.Interaction):
        """Remove a term."""
        term_index = int(interaction.data['values'][0])
        removed_term = self.term_list.pop(term_index)
        
        embed = discord.Embed(
            title="✅ Term Removed",
            description=f"Removed `{removed_term}` from {self.title.lower()}.",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Refresh the list
        await self.show_list(interaction)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_list(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.term_list) - 1) // 10
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_list(interaction)


class AddTermModal(discord.ui.Modal):
    """Modal for adding terms to lists."""
    
    def __init__(self, term_list: List[str], list_title: str):
        super().__init__(title=f"Add to {list_title}")
        self.term_list = term_list
        self.list_title = list_title
        
        self.term_input = discord.ui.TextInput(
            label="Term to add",
            placeholder="Enter the term (supports * wildcards)",
            required=True,
            max_length=100
        )
        self.add_item(self.term_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle term addition."""
        term = self.term_input.value.strip().lower()
        
        if term in self.term_list:
            embed = discord.Embed(
                title="❌ Duplicate Term",
                description=f"The term `{term}` is already in the list.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        self.term_list.append(term)
        
        embed = discord.Embed(
            title="✅ Term Added",
            description=f"Added `{term}` to {self.list_title.lower()}.",
            color=discord.Color.green()
        )
        
        if '*' in term:
            embed.add_field(
                name="Wildcard Note",
                value="This term uses wildcards and will match partial words.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class WatchChannelsView(discord.ui.View):
    """Configure watched channels for moderation."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.watch_channels = []
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display watch channels settings."""
        embed = discord.Embed(
            title="👁️ Watched Channels",
            description="Channels where moderation filters are active",
            color=discord.Color.blue()
        )
        
        if not self.watch_channels:
            embed.add_field(
                name="Status",
                value="No channels being watched",
                inline=False
            )
        else:
            channel_mentions = []
            for channel_id in self.watch_channels:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
            
            embed.add_field(
                name=f"Watched Channels ({len(channel_mentions)})",
                value="\n".join(channel_mentions) if channel_mentions else "None",
                inline=False
            )
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Channel selector
        channel_select = discord.ui.ChannelSelect(
            placeholder="Add channels to watch...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            max_values=10
        )
        channel_select.callback = self.add_channels
        self.add_item(channel_select)
        
        if self.watch_channels:
            # Remove channels
            clear_button = discord.ui.Button(
                label="Clear All",
                style=discord.ButtonStyle.danger,
                emoji="🗑️"
            )
            clear_button.callback = self.clear_channels
            self.add_item(clear_button)
    
    async def add_channels(self, interaction: discord.Interaction):
        """Add channels to watch list."""
        selected_channels = interaction.data['values']
        added_channels = []
        
        for channel_id_str in selected_channels:
            channel_id = int(channel_id_str)
            if channel_id not in self.watch_channels:
                self.watch_channels.append(channel_id)
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    added_channels.append(channel.mention)
        
        if added_channels:
            embed = discord.Embed(
                title="✅ Channels Added",
                description=f"Added {len(added_channels)} channel(s) to watch list:\n" + "\n".join(added_channels),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Changes",
                description="All selected channels were already being watched.",
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_settings(interaction)
    
    async def clear_channels(self, interaction: discord.Interaction):
        """Clear all watched channels."""
        self.watch_channels.clear()
        
        embed = discord.Embed(
            title="🗑️ Channels Cleared",
            description="Removed all channels from watch list.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_settings(interaction)


class StaffExemptionsView(discord.ui.View):
    """Configure staff role exemptions."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.staff_roles = []
    
    async def show_settings(self, interaction: discord.Interaction):
        """Display staff exemptions."""
        embed = discord.Embed(
            title="🛡️ Staff Exemptions",
            description="Roles exempt from moderation filters",
            color=discord.Color.gold()
        )
        
        if not self.staff_roles:
            embed.add_field(
                name="Status",
                value="No staff roles configured",
                inline=False
            )
        else:
            role_mentions = []
            for role_id in self.staff_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            
            embed.add_field(
                name=f"Exempt Roles ({len(role_mentions)})",
                value="\n".join(role_mentions) if role_mentions else "None",
                inline=False
            )
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    def update_buttons(self):
        """Update view buttons."""
        self.clear_items()
        
        # Role selector
        role_select = discord.ui.RoleSelect(
            placeholder="Add exempt roles...",
            max_values=10
        )
        role_select.callback = self.add_roles
        self.add_item(role_select)
        
        if self.staff_roles:
            # Clear button
            clear_button = discord.ui.Button(
                label="Clear All",
                style=discord.ButtonStyle.danger,
                emoji="🗑️"
            )
            clear_button.callback = self.clear_roles
            self.add_item(clear_button)
    
    async def add_roles(self, interaction: discord.Interaction):
        """Add roles to exemption list."""
        selected_roles = interaction.data['resolved']['roles']
        added_roles = []
        
        for role_id_str, role_data in selected_roles.items():
            role_id = int(role_id_str)
            if role_id not in self.staff_roles:
                self.staff_roles.append(role_id)
                added_roles.append(f"<@&{role_id}>")
        
        if added_roles:
            embed = discord.Embed(
                title="✅ Roles Added",
                description=f"Added {len(added_roles)} role(s) to exemption list:\n" + "\n".join(added_roles),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Changes",
                description="All selected roles were already exempt.",
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_settings(interaction)
    
    async def clear_roles(self, interaction: discord.Interaction):
        """Clear all exempt roles."""
        self.staff_roles.clear()
        
        embed = discord.Embed(
            title="🗑️ Roles Cleared",
            description="Removed all roles from exemption list.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.show_settings(interaction)


class RoleManagerView(discord.ui.View):
    """Role management interface."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.selected_user = None
        self.selected_roles = []
    
    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select a user to manage..."
    )
    async def user_select(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        """Select user for role management."""
        self.selected_user = select.values[0]
        
        embed = discord.Embed(
            title="🎭 Role Management",
            description=f"Managing roles for {self.selected_user.mention}",
            color=discord.Color.blue()
        )
        
        current_roles = [role for role in self.selected_user.roles if role != interaction.guild.default_role]
        if current_roles:
            embed.add_field(
                name="Current Roles",
                value="\n".join(role.mention for role in current_roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Current Roles",
                value="No roles",
                inline=False
            )
        
        view = UserRoleManagerView(self.selected_user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class UserRoleManagerView(discord.ui.View):
    """Role management for a specific user."""
    
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300)
        self.user = user
    
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select roles to assign...",
        max_values=10
    )
    async def assign_roles(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        """Assign roles to user."""
        if not PermissionChecker.can_manage_roles(interaction.user, interaction.guild.me):
            embed = PermissionChecker.get_permission_error_embed(
                "manage roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        roles_to_add = []
        failed_roles = []
        
        for role in select.values:
            if role in self.user.roles:
                continue  # User already has this role
            
            if not PermissionChecker.can_assign_role(interaction.guild.me, role):
                failed_roles.append(role)
            else:
                roles_to_add.append(role)
        
        # Add roles
        if roles_to_add:
            try:
                await self.user.add_roles(*roles_to_add, reason=f"Role assignment by {interaction.user}")
                
                embed = discord.Embed(
                    title="✅ Roles Assigned",
                    description=f"Successfully assigned {len(roles_to_add)} role(s) to {self.user.mention}:",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Added Roles",
                    value="\n".join(role.mention for role in roles_to_add),
                    inline=False
                )
                
                # Log action
                bot = interaction.client
                await bot.log_action(
                    interaction.guild_id,
                    "Role Assignment",
                    interaction.user,
                    self.user,
                    f"Added roles: {', '.join(role.name for role in roles_to_add)}"
                )
                
            except discord.Forbidden:
                embed = PermissionChecker.get_bot_permission_error_embed(
                    "assign these roles",
                    "Manage Roles (with proper role hierarchy)"
                )
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to assign roles: {str(e)}",
                    color=discord.Color.red()
                )
        else:
            embed = discord.Embed(
                title="ℹ️ No Changes",
                description="No new roles were assigned.",
                color=discord.Color.blue()
            )
        
        if failed_roles:
            embed.add_field(
                name="⚠️ Failed Assignments",
                value=f"Cannot assign these roles (hierarchy issue):\n" + 
                     "\n".join(role.mention for role in failed_roles),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Remove Roles", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open role removal interface."""
        current_roles = [role for role in self.user.roles if role != interaction.guild.default_role]
        
        if not current_roles:
            embed = discord.Embed(
                title="ℹ️ No Roles",
                description=f"{self.user.mention} has no roles to remove.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        view = RoleRemovalView(self.user, current_roles)
        
        embed = discord.Embed(
            title="➖ Remove Roles",
            description=f"Select roles to remove from {self.user.mention}:",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RoleRemovalView(discord.ui.View):
    """View for removing roles from users."""
    
    def __init__(self, user: discord.Member, current_roles: List[discord.Role]):
        super().__init__(timeout=300)
        self.user = user
        
        # Create dropdown with current roles
        if len(current_roles) <= 25:  # Discord limit
            options = [
                discord.SelectOption(
                    label=role.name,
                    value=str(role.id),
                    description=f"Color: {str(role.color)}" if role.color != discord.Color.default() else "No color"
                )
                for role in current_roles
            ]
            
            select = discord.ui.Select(
                placeholder="Select roles to remove...",
                options=options,
                max_values=len(options)
            )
            select.callback = self.remove_roles
            self.add_item(select)
    
    async def remove_roles(self, interaction: discord.Interaction):
        """Remove selected roles."""
        if not PermissionChecker.can_manage_roles(interaction.user, interaction.guild.me):
            embed = PermissionChecker.get_permission_error_embed(
                "manage roles",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        role_ids = [int(role_id) for role_id in interaction.data['values']]
        roles_to_remove = [interaction.guild.get_role(role_id) for role_id in role_ids]
        roles_to_remove = [role for role in roles_to_remove if role]  # Filter None values
        
        if not roles_to_remove:
            await interaction.response.send_message("No valid roles selected.", ephemeral=True)
            return
        
        try:
            await self.user.remove_roles(*roles_to_remove, reason=f"Role removal by {interaction.user}")
            
            embed = discord.Embed(
                title="✅ Roles Removed",
                description=f"Successfully removed {len(roles_to_remove)} role(s) from {self.user.mention}:",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Removed Roles",
                value="\n".join(role.mention for role in roles_to_remove),
                inline=False
            )
            
            # Log action
            bot = interaction.client
            await bot.log_action(
                interaction.guild_id,
                "Role Removal",
                interaction.user,
                self.user,
                f"Removed roles: {', '.join(role.name for role in roles_to_remove)}"
            )
            
        except discord.Forbidden:
            embed = PermissionChecker.get_bot_permission_error_embed(
                "remove these roles",
                "Manage Roles (with proper role hierarchy)"
            )
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove roles: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ReportModal(discord.ui.Modal):
    """Modal for reporting inappropriate content."""
    
    def __init__(self):
        super().__init__(title="Report Inappropriate Content")
        
        self.message_link_input = discord.ui.TextInput(
            label="Message Link (Optional)",
            placeholder="Right-click message → Copy Message Link",
            required=False,
            max_length=200
        )
        self.add_item(self.message_link_input)
        
        self.reason_input = discord.ui.TextInput(
            label="Reason for Report",
            placeholder="Describe why you're reporting this content...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle report submission."""
        message_link = self.message_link_input.value.strip()
        reason = self.reason_input.value.strip()
        
        # Create incident record
        async with get_session() as session:
            incident = ModerationIncident(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                channel_id=interaction.channel_id,
                type="manual_report",
                reason=reason,
                message_snapshot={"message_link": message_link} if message_link else None
            )
            session.add(incident)
            await session.commit()
        
        # Send to moderation logs
        bot = interaction.client
        guild_config = await bot.get_guild_config(interaction.guild_id)
        
        if guild_config and guild_config.logs_channel_id:
            log_channel = bot.get_channel(guild_config.logs_channel_id)
            if log_channel:
                embed = discord.Embed(
                    title="🚨 Content Report",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(name="Reporter", value=interaction.user.mention, inline=True)
                embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                
                if message_link:
                    embed.add_field(name="Message Link", value=message_link, inline=False)
                
                embed.set_footer(text=f"Report ID: {incident.id}")
                
                try:
                    await log_channel.send(embed=embed)
                except Exception:
                    pass  # Silently fail if can't send to logs
        
        # Confirm to user
        embed = discord.Embed(
            title="✅ Report Submitted",
            description="Your report has been submitted to the moderation team. Thank you for helping keep our community safe!",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class IncidentLogView(discord.ui.View):
    """View recent moderation incidents."""
    
    def __init__(self):
        super().__init__(timeout=300)
        self.current_page = 0
        self.incidents = []
    
    async def show_incidents(self, interaction: discord.Interaction):
        """Display recent moderation incidents."""
        await self.load_incidents(interaction.guild_id)
        
        embed = discord.Embed(
            title="📋 Recent Moderation Incidents",
            color=discord.Color.orange()
        )
        
        if not self.incidents:
            embed.description = "No incidents recorded in the last 30 days."
        else:
            # Pagination
            per_page = 5
            start_idx = self.current_page * per_page
            end_idx = start_idx + per_page
            page_incidents = self.incidents[start_idx:end_idx]
            
            for incident in page_incidents:
                user = interaction.guild.get_member(incident.user_id)
                user_name = user.display_name if user else f"User {incident.user_id}"
                
                channel = interaction.guild.get_channel(incident.channel_id)
                channel_name = channel.mention if channel else f"Channel {incident.channel_id}"
                
                embed.add_field(
                    name=f"{incident.type.replace('_', ' ').title()} - {discord.utils.format_dt(incident.created_at, 'R')}",
                    value=(
                        f"**User:** {user_name}\n"
                        f"**Channel:** {channel_name}\n"
                        f"**Action:** {incident.action_taken or 'None'}\n"
                        f"**Reason:** {incident.reason[:100]}{'...' if len(incident.reason or '') > 100 else ''}"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page + 1} of {(len(self.incidents) - 1) // per_page + 1}")
        
        self.update_buttons()
        
        if hasattr(interaction, 'response') and not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        else:
            await interaction.edit_original_response(embed=embed, view=self)
    
    async def load_incidents(self, guild_id: int):
        """Load recent incidents from database."""
        async with get_session() as session:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            result = await session.execute(
                select(ModerationIncident)
                .where(
                    and_(
                        ModerationIncident.guild_id == guild_id,
                        ModerationIncident.created_at >= thirty_days_ago
                    )
                )
                .order_by(ModerationIncident.created_at.desc())
            )
            self.incidents = result.scalars().all()
    
    def update_buttons(self):
        """Update navigation buttons."""
        self.clear_items()
        
        per_page = 5
        
        if self.current_page > 0:
            prev_button = discord.ui.Button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
            prev_button.callback = self.previous_page
            self.add_item(prev_button)
        
        if (self.current_page + 1) * per_page < len(self.incidents):
            next_button = discord.ui.Button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
    
    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.current_page = max(0, self.current_page - 1)
        await self.show_incidents(interaction)
    
    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        max_page = (len(self.incidents) - 1) // 5
        self.current_page = min(max_page, self.current_page + 1)
        await self.show_incidents(interaction)