"""
Management commands for the Guild Management Bot
Includes migration commands for populating initial data.
"""
import discord
from discord.ext import commands
from typing import Optional

from sqlalchemy import select

from database import OnboardingQuestion, get_session
from migrations.initial_data import migrate_guild_data
from utils.permissions import PermissionChecker


class Management(commands.Cog):
    """Administrative management commands."""

    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(
        name="migrate",
        description="Populate database with initial onboarding questions and rules"
    )
    @discord.app_commands.describe(
        action="What to migrate",
        force="Force migration even if data already exists"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="onboarding-questions", value="questions"),
        discord.app_commands.Choice(name="role-rules", value="rules"),
        discord.app_commands.Choice(name="all-data", value="all"),
        discord.app_commands.Choice(name="check-status", value="status")
    ])
    async def migrate(
            self,
            interaction: discord.Interaction,
            action: discord.app_commands.Choice[str],
            force: bool = False
    ):
        """Migrate initial data to the database."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "run migrations",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            if action.value == "status":
                await self._check_migration_status(interaction)
            elif action.value == "questions":
                await self._migrate_questions(interaction, force)
            elif action.value == "rules":
                await self._migrate_rules(interaction, force)
            elif action.value == "all":
                await self._migrate_all_data(interaction, force)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Migration Failed",
                description=f"An error occurred during migration: {str(e)}",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Troubleshooting",
                value=(
                    "• Check bot permissions\n"
                    "• Verify database connectivity\n"
                    "• Contact support if the issue persists"
                ),
                inline=False
            )
            await interaction.followup.send(embed=embed)

    async def _check_migration_status(self, interaction: discord.Interaction):
        """Check the current migration status."""
        async with get_session() as session:
            # Count existing onboarding questions
            from sqlalchemy import select, func
            from database import OnboardingQuestion, OnboardingRule

            questions_result = await session.execute(
                select(func.count(OnboardingQuestion.id))
                .where(OnboardingQuestion.guild_id == interaction.guild_id)
            )
            question_count = questions_result.scalar()

            rules_result = await session.execute(
                select(func.count(OnboardingRule.id))
                .where(OnboardingRule.guild_id == interaction.guild_id)
            )
            rules_count = rules_result.scalar()

            # Get active questions for details
            active_questions = await session.execute(
                select(OnboardingQuestion)
                .where(
                    OnboardingQuestion.guild_id == interaction.guild_id,
                    OnboardingQuestion.is_active == True
                )
                .order_by(OnboardingQuestion.position)
            )
            questions = active_questions.scalars().all()

        embed = discord.Embed(
            title="📊 Migration Status",
            description=f"Current database state for **{interaction.guild.name}**",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📋 Onboarding Questions",
            value=f"**Total:** {question_count}\n**Active:** {len(questions)}",
            inline=True
        )

        embed.add_field(
            name="⚙️ Role Rules",
            value=f"**Total:** {rules_count}",
            inline=True
        )

        # Show question types if we have questions
        if questions:
            question_types = {}
            for q in questions:
                question_types[q.type] = question_types.get(q.type, 0) + 1

            type_list = [f"**{q_type}:** {count}" for q_type, count in question_types.items()]
            embed.add_field(
                name="Question Types",
                value="\n".join(type_list),
                inline=True
            )

        # Migration recommendations
        recommendations = []
        if question_count == 0:
            recommendations.append("• No onboarding questions - run migration to add default questions")
        if rules_count == 0:
            recommendations.append("• No role rules - run migration to add suggestion rules")
        if question_count < 5:
            recommendations.append("• Consider adding more questions for better onboarding")

        if recommendations:
            embed.add_field(
                name="💡 Recommendations",
                value="\n".join(recommendations),
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Status",
                value="Your server has a good onboarding setup!",
                inline=False
            )

        embed.add_field(
            name="🔧 Migration Commands",
            value=(
                "• `/migrate all-data` - Add all default data\n"
                "• `/migrate onboarding-questions` - Add just questions\n"
                "• `/migrate role-rules` - Add just role rules\n"
                "• Add `force:True` to overwrite existing data"
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed)

    async def _migrate_questions(self, interaction: discord.Interaction, force: bool):
        """Migrate onboarding questions."""
        # Import here to avoid circular imports
        from migrations.initial_data import populate_onboarding_questions

        # Check if questions already exist (unless forcing)
        if not force:
            async with get_session() as session:
                existing = await session.execute(
                    select(OnboardingQuestion)
                    .where(OnboardingQuestion.guild_id == interaction.guild_id)
                    .limit(1)
                )
                if existing.scalar_one_or_none():
                    embed = discord.Embed(
                        title="⚠️ Questions Already Exist",
                        description="Onboarding questions already exist for this server. Use `force:True` to overwrite.",
                        color=discord.Color.orange()
                    )
                    await interaction.followup.send(embed=embed)
                    return

        # Run migration
        questions_added = await populate_onboarding_questions(interaction.guild_id)

        embed = discord.Embed(
            title="✅ Questions Migration Complete",
            description=f"Successfully added **{questions_added}** onboarding questions!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="What's Next?",
            value=(
                "1. Test the onboarding process in Member Hub\n"
                "2. Customize questions in Admin Dashboard → Configuration\n"
                "3. Set up role suggestion rules with `/migrate role-rules`"
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed)

    async def _migrate_rules(self, interaction: discord.Interaction, force: bool):
        """Migrate role suggestion rules."""
        from migrations.initial_data import populate_role_rules

        # Create role mapping from Discord roles
        role_mapping = {}
        common_role_names = [
            "Newbie", "Beginner", "Learning", "Casual", "Weekend Warrior",
            "Hardcore", "Dedicated", "Core Member", "Competitive", "Pro Player", "Elite",
            "PvE", "Raider", "PvE Enthusiast", "PvP", "Gladiator", "PvP Enthusiast",
            "Tank", "Guardian", "Protector", "DPS", "Striker", "Damage Dealer",
            "Support", "Healer", "Medic", "Voice Active", "Communicator",
            "Text Only", "Quiet Member", "Member", "Verified", "Active"
        ]

        for role in interaction.guild.roles:
            if role.name in common_role_names:
                role_mapping[role.name] = role.id

        # Run migration
        rules_added = await populate_role_rules(interaction.guild_id, role_mapping)

        embed = discord.Embed(
            title="✅ Rules Migration Complete",
            description=f"Successfully added **{rules_added}** role suggestion rules!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Role Mapping",
            value=f"Mapped **{len(role_mapping)}** Discord roles to rule suggestions",
            inline=True
        )

        if role_mapping:
            role_list = [f"• {name}" for name in list(role_mapping.keys())[:10]]
            if len(role_mapping) > 10:
                role_list.append(f"• ... and {len(role_mapping) - 10} more")

            embed.add_field(
                name="Mapped Roles",
                value="\n".join(role_list),
                inline=True
            )

        embed.add_field(
            name="What's Next?",
            value=(
                "1. Test onboarding to see role suggestions in action\n"
                "2. Create additional Discord roles for better mapping\n"
                "3. Customize rules in Admin Dashboard → Configuration"
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed)

    async def _migrate_all_data(self, interaction: discord.Interaction, force: bool):
        """Migrate all data (questions and rules)."""
        embed = discord.Embed(
            title="🚀 Running Full Migration",
            description="Adding onboarding questions and role suggestion rules...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)

        # Run full migration with role mapping
        result = await migrate_guild_data(interaction.guild_id, self.bot)

        embed = discord.Embed(
            title="✅ Full Migration Complete",
            description="Successfully set up your server's onboarding system!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="📊 Results",
            value=(
                f"**Questions Added:** {result['questions_added']}\n"
                f"**Rules Added:** {result['rules_added']}"
            ),
            inline=True
        )

        embed.add_field(
            name="🎯 Features Added",
            value=(
                "• Gaming experience questions\n"
                "• Timezone selection\n"
                "• Play style preferences\n"
                "• Role-based suggestions\n"
                "• Communication preferences"
            ),
            inline=True
        )

        embed.add_field(
            name="🚀 Next Steps",
            value=(
                "1. **Test Onboarding** → Member Hub → Start Onboarding\n"
                "2. **Review Settings** → Admin Dashboard → Configuration\n"
                "3. **Deploy Panels** → Use `/deploy_panels` if not done yet\n"
                "4. **Customize** → Add/edit questions to match your community"
            ),
            inline=False
        )

        embed.set_footer(text="💡 Tip: Use the Admin Testing feature in Moderation Center to test onboarding!")

        await interaction.edit_original_response(embed=embed)

    @discord.app_commands.command(
        name="database-info",
        description="Show database information and statistics"
    )
    async def database_info(self, interaction: discord.Interaction):
        """Show database information and statistics."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view database info",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            from database import (
                OnboardingQuestion, OnboardingRule, OnboardingSession,
                Character, User, Poll, Announcement, ModerationIncident
            )
            from sqlalchemy import func

            async with get_session() as session:
                # Count various records for this guild
                questions_count = await session.scalar(
                    select(func.count(OnboardingQuestion.id))
                    .where(OnboardingQuestion.guild_id == interaction.guild_id)
                )

                rules_count = await session.scalar(
                    select(func.count(OnboardingRule.id))
                    .where(OnboardingRule.guild_id == interaction.guild_id)
                )

                sessions_count = await session.scalar(
                    select(func.count(OnboardingSession.id))
                    .where(OnboardingSession.guild_id == interaction.guild_id)
                )

                characters_count = await session.scalar(
                    select(func.count(Character.id))
                    .where(Character.guild_id == interaction.guild_id)
                )

                users_count = await session.scalar(
                    select(func.count(User.id))
                    .where(User.guild_id == interaction.guild_id)
                )

                polls_count = await session.scalar(
                    select(func.count(Poll.id))
                    .where(Poll.guild_id == interaction.guild_id)
                )

                announcements_count = await session.scalar(
                    select(func.count(Announcement.id))
                    .where(Announcement.guild_id == interaction.guild_id)
                )

                incidents_count = await session.scalar(
                    select(func.count(ModerationIncident.id))
                    .where(ModerationIncident.guild_id == interaction.guild_id)
                )

            embed = discord.Embed(
                title="🗄️ Database Information",
                description=f"Database statistics for **{interaction.guild.name}**",
                color=discord.Color.blue()
            )

            # Onboarding data
            embed.add_field(
                name="📋 Onboarding System",
                value=(
                    f"**Questions:** {questions_count}\n"
                    f"**Rules:** {rules_count}\n"
                    f"**Sessions:** {sessions_count}"
                ),
                inline=True
            )

            # User data
            embed.add_field(
                name="👤 User Data",
                value=(
                    f"**Users:** {users_count}\n"
                    f"**Characters:** {characters_count}"
                ),
                inline=True
            )

            # Content data
            embed.add_field(
                name="📊 Content",
                value=(
                    f"**Polls:** {polls_count}\n"
                    f"**Announcements:** {announcements_count}\n"
                    f"**Mod Incidents:** {incidents_count}"
                ),
                inline=True
            )

            # Health check
            total_records = (questions_count + rules_count + sessions_count +
                             characters_count + users_count + polls_count +
                             announcements_count + incidents_count)

            if total_records == 0:
                health_status = "🔴 Empty - Run migrations to populate"
                health_color = discord.Color.red()
            elif questions_count == 0:
                health_status = "🟡 Missing onboarding questions"
                health_color = discord.Color.orange()
            else:
                health_status = "🟢 Healthy"
                health_color = discord.Color.green()

            embed.add_field(
                name="💊 Database Health",
                value=f"**Status:** {health_status}\n**Total Records:** {total_records}",
                inline=False
            )

            embed.color = health_color

        except Exception as e:
            embed = discord.Embed(
                title="❌ Database Error",
                description=f"Failed to retrieve database information: {str(e)}",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(Management(bot))