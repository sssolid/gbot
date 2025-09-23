"""
Role management views for the Guild Management Bot
"""
from typing import List

import discord


class RoleManagerView(discord.ui.View):
    """Main role management interface."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_role_interface(self, interaction: discord.Interaction):
        """Show the role management interface."""
        embed = discord.Embed(
            title="🎭 Role Management",
            description="Manage server roles and member assignments",
            color=discord.Color.blue()
        )

        # Get role counts
        guild = interaction.guild
        total_roles = len([r for r in guild.roles if r != guild.default_role])

        embed.add_field(
            name="Server Roles",
            value=f"{total_roles} roles configured",
            inline=True
        )

        embed.add_field(
            name="Members",
            value=f"{guild.member_count} total members",
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Browse Members", style=discord.ButtonStyle.primary, emoji="👥")
    async def browse_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Browse server members for role management."""
        view = MemberBrowserView()
        await view.show_members(interaction)

    @discord.ui.button(label="Role Statistics", style=discord.ButtonStyle.secondary, emoji="📊")
    async def role_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show role usage statistics."""
        embed = discord.Embed(
            title="📊 Role Statistics",
            description="Current role distribution",
            color=discord.Color.green()
        )

        guild = interaction.guild
        role_counts = {}

        for member in guild.members:
            if member.bot:
                continue
            for role in member.roles:
                if role == guild.default_role:
                    continue
                role_counts[role.name] = role_counts.get(role.name, 0) + 1

        if role_counts:
            sorted_roles = sorted(role_counts.items(), key=lambda x: x[1], reverse=True)
            for role_name, count in sorted_roles[:20]:  # Show top 20 roles
                embed.add_field(
                    name=role_name,
                    value=f"{count} members",
                    inline=True
                )
        else:
            embed.add_field(
                name="No Role Data",
                value="No roles assigned to members",
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Mass Role Actions", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def mass_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mass role assignment/removal actions."""
        view = MassRoleActionView()
        await view.show_mass_actions(interaction)


class MemberBrowserView(discord.ui.View):
    """Browse members for role management."""

    def __init__(self, page: int = 0):
        super().__init__(timeout=300)
        self.page = page
        self.members_per_page = 20

    async def show_members(self, interaction: discord.Interaction):
        """Show paginated member list."""
        guild = interaction.guild
        members = [m for m in guild.members if not m.bot]

        total_pages = (len(members) - 1) // self.members_per_page + 1
        start_idx = self.page * self.members_per_page
        end_idx = min(start_idx + self.members_per_page, len(members))
        page_members = members[start_idx:end_idx]

        embed = discord.Embed(
            title="👥 Server Members",
            description=f"Page {self.page + 1} of {total_pages}",
            color=discord.Color.blue()
        )

        # Create member select menu
        options = []
        for member in page_members[:25]:  # Discord limit
            role_count = len([r for r in member.roles if r != guild.default_role])
            options.append(discord.SelectOption(
                label=member.display_name[:100],
                description=f"{role_count} roles",
                value=str(member.id),
                emoji="👤"
            ))

        if options:
            select = MemberSelectMenu(options)
            self.add_item(select)

        # Add navigation buttons if needed
        if total_pages > 1:
            if self.page > 0:
                prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⬅️")
                prev_button.callback = self.previous_page
                self.add_item(prev_button)

            if self.page < total_pages - 1:
                next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, emoji="➡️")
                next_button.callback = self.next_page
                self.add_item(next_button)

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        self.page = max(0, self.page - 1)
        self.clear_items()
        await self.show_members(interaction)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        self.page += 1
        self.clear_items()
        await self.show_members(interaction)


class MemberSelectMenu(discord.ui.Select):
    """Select menu for choosing a member to manage."""

    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="Select a member to manage...",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle member selection."""
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)

        if not member:
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return

        view = MemberRoleManagementView(member)
        await view.show_member_roles(interaction)


class MemberRoleManagementView(discord.ui.View):
    """Manage roles for a specific member."""

    def __init__(self, member: discord.Member):
        super().__init__(timeout=300)
        self.member = member

    async def show_member_roles(self, interaction: discord.Interaction):
        """Show role management for the member."""
        embed = discord.Embed(
            title=f"🎭 Managing {self.member.display_name}",
            color=discord.Color.blue()
        )

        current_roles = [role for role in self.member.roles if role != interaction.guild.default_role]
        if current_roles:
            embed.add_field(
                name="Current Roles",
                value="\n".join(role.mention for role in current_roles),
                inline=False
            )
        else:
            embed.add_field(
                name="Current Roles",
                value="No roles assigned",
                inline=False
            )

        embed.set_thumbnail(url=self.member.display_avatar.url)

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Add roles...",
        max_values=20
    )
    async def add_roles(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        """Add roles to the member."""
        roles_to_add = [role for role in select.values if role not in self.member.roles]

        if not roles_to_add:
            await interaction.response.send_message("Member already has all selected roles.", ephemeral=True)
            return

        try:
            await self.member.add_roles(*roles_to_add, reason=f"Role assignment by {interaction.user}")

            embed = discord.Embed(
                title="✅ Roles Added",
                description=f"Added {len(roles_to_add)} role(s) to {self.member.mention}",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Added Roles",
                value="\n".join(role.mention for role in roles_to_add),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to assign these roles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to assign roles: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remove Roles", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_roles_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show role removal interface."""
        current_roles = [role for role in self.member.roles if role != interaction.guild.default_role]

        if not current_roles:
            await interaction.response.send_message("Member has no roles to remove.", ephemeral=True)
            return

        view = RoleRemovalView(self.member, current_roles)

        embed = discord.Embed(
            title=f"➖ Remove Roles from {self.member.display_name}",
            description="Select roles to remove:",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class RoleRemovalView(discord.ui.View):
    """View for removing roles from a member."""

    def __init__(self, member: discord.Member, roles: List[discord.Role]):
        super().__init__(timeout=300)
        self.member = member

        # Create options for role removal
        options = []
        for role in roles[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=role.name,
                description=f"Remove {role.name}",
                value=str(role.id),
                emoji="➖"
            ))

        if options:
            select = discord.ui.Select(
                placeholder="Select roles to remove...",
                options=options,
                max_values=min(len(options), 25)
            )
            select.callback = self.remove_selected_roles
            self.add_item(select)

    async def remove_selected_roles(self, interaction: discord.Interaction):
        """Remove selected roles from member."""
        role_ids = [int(value) for value in interaction.data['values']]
        roles_to_remove = [interaction.guild.get_role(role_id) for role_id in role_ids]
        roles_to_remove = [role for role in roles_to_remove if role and role in self.member.roles]

        if not roles_to_remove:
            await interaction.response.send_message("No valid roles selected for removal.", ephemeral=True)
            return

        try:
            await self.member.remove_roles(*roles_to_remove, reason=f"Role removal by {interaction.user}")

            embed = discord.Embed(
                title="✅ Roles Removed",
                description=f"Removed {len(roles_to_remove)} role(s) from {self.member.mention}",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Removed Roles",
                value="\n".join(role.mention for role in roles_to_remove),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to remove these roles.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to remove roles: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class MassRoleActionView(discord.ui.View):
    """Mass role assignment/removal actions."""

    def __init__(self):
        super().__init__(timeout=300)

    async def show_mass_actions(self, interaction: discord.Interaction):
        """Show mass action options."""
        embed = discord.Embed(
            title="⚡ Mass Role Actions",
            description="Perform bulk role operations",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="⚠️ Warning",
            value="Mass actions affect multiple members at once. Use with caution.",
            inline=False
        )

        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(label="Mass Add Role", style=discord.ButtonStyle.primary, emoji="➕")
    async def mass_add_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mass add a role to members."""
        modal = MassRoleModal("add")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Mass Remove Role", style=discord.ButtonStyle.danger, emoji="➖")
    async def mass_remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mass remove a role from members."""
        modal = MassRoleModal("remove")
        await interaction.response.send_modal(modal)


class MassRoleModal(discord.ui.Modal):
    """Modal for mass role operations."""

    def __init__(self, action: str):
        title = f"Mass {'Add' if action == 'add' else 'Remove'} Role"
        super().__init__(title=title)
        self.action = action

        self.role_input = discord.ui.TextInput(
            label="Role Name",
            placeholder="Enter the exact role name...",
            required=True,
            max_length=100
        )

        self.reason_input = discord.ui.TextInput(
            label="Reason",
            placeholder="Reason for this mass action...",
            required=False,
            max_length=200
        )

        self.add_item(self.role_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle mass role operation."""
        role_name = self.role_input.value.strip()
        reason = self.reason_input.value.strip() or f"Mass {self.action} by {interaction.user}"

        # Find the role
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            embed = discord.Embed(
                title="❌ Role Not Found",
                description=f"Could not find a role named '{role_name}'",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get members to modify
        if self.action == "add":
            members_to_modify = [m for m in interaction.guild.members if not m.bot and role not in m.roles]
        else:
            members_to_modify = [m for m in interaction.guild.members if not m.bot and role in m.roles]

        if not members_to_modify:
            action_text = "add to" if self.action == "add" else "remove from"
            embed = discord.Embed(
                title="ℹ️ No Changes Needed",
                description=f"No members need the role '{role.name}' {action_text}.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Confirm the action
        view = MassRoleConfirmationView(role, members_to_modify, self.action, reason)

        embed = discord.Embed(
            title="⚠️ Confirm Mass Action",
            description=f"**{self.action.title()} role '{role.name}' {'to' if self.action == 'add' else 'from'} {len(members_to_modify)} members?**",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Affected Members",
            value=str(len(members_to_modify)),
            inline=True
        )

        embed.add_field(
            name="Action",
            value=self.action.title(),
            inline=True
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class MassRoleConfirmationView(discord.ui.View):
    """Confirmation view for mass role operations."""

    def __init__(self, role: discord.Role, members: List[discord.Member], action: str, reason: str):
        super().__init__(timeout=300)
        self.role = role
        self.members = members
        self.action = action
        self.reason = reason

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Execute the mass role operation."""
        await interaction.response.defer(ephemeral=True)

        success_count = 0
        failed_count = 0

        for member in self.members:
            try:
                if self.action == "add":
                    await member.add_roles(self.role, reason=self.reason)
                else:
                    await member.remove_roles(self.role, reason=self.reason)
                success_count += 1
            except Exception:
                failed_count += 1

        embed = discord.Embed(
            title="✅ Mass Action Complete",
            description=f"Role '{self.role.name}' {self.action} operation finished",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Successful",
            value=str(success_count),
            inline=True
        )

        if failed_count > 0:
            embed.add_field(
                name="Failed",
                value=str(failed_count),
                inline=True
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the mass role operation."""
        embed = discord.Embed(
            title="❌ Action Cancelled",
            description="Mass role operation cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)