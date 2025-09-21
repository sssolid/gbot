"""
Onboarding cog for the Guild Management Bot
"""
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_

from database import OnboardingSession, OnboardingQuestion, get_session
from views.onboarding import OnboardingWizard
from utils.permissions import PermissionChecker


class OnboardingCog(commands.Cog):
    """Handles onboarding-related commands and events."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="onboarding", description="Start or continue the onboarding process")
    async def onboarding_command(self, interaction: discord.Interaction):
        """Start onboarding process via slash command."""
        # Check if user has an existing session
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.user_id == interaction.user.id,
                        OnboardingSession.guild_id == interaction.guild_id,
                        OnboardingSession.state == 'in_progress'
                    )
                )
            )
            existing_session = result.scalar_one_or_none()
        
        if existing_session:
            embed = discord.Embed(
                title="📝 Continue Onboarding",
                description="You have an onboarding session in progress. Would you like to continue?",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="🚀 Start Onboarding",
                description="Welcome! Let's get you set up in this server.",
                color=discord.Color.green()
            )
        
        view = OnboardingWizard(existing_session.id if existing_session else None)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="onboarding_status", description="Check your onboarding status")
    async def onboarding_status(self, interaction: discord.Interaction):
        """Check onboarding status."""
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.user_id == interaction.user.id,
                        OnboardingSession.guild_id == interaction.guild_id
                    )
                )
                .order_by(OnboardingSession.created_at.desc())
                .limit(1)
            )
            latest_session = result.scalar_one_or_none()
        
        if not latest_session:
            embed = discord.Embed(
                title="📝 Onboarding Status",
                description="You haven't started the onboarding process yet. Use `/onboarding` to begin!",
                color=discord.Color.blue()
            )
        else:
            status_colors = {
                'in_progress': discord.Color.yellow(),
                'completed': discord.Color.orange(),
                'approved': discord.Color.green(),
                'denied': discord.Color.red()
            }
            
            status_messages = {
                'in_progress': "Your onboarding is in progress. Continue where you left off!",
                'completed': "Your onboarding is complete and under review by administrators.",
                'approved': "Your onboarding has been approved! Welcome to the server!",
                'denied': f"Your onboarding was denied. Reason: {latest_session.denial_reason or 'No reason provided'}"
            }
            
            embed = discord.Embed(
                title="📝 Onboarding Status",
                description=status_messages.get(latest_session.state, "Unknown status"),
                color=status_colors.get(latest_session.state, discord.Color.blue())
            )
            
            embed.add_field(
                name="Started",
                value=discord.utils.format_dt(latest_session.created_at, 'R'),
                inline=True
            )
            
            if latest_session.completed_at:
                embed.add_field(
                    name="Completed",
                    value=discord.utils.format_dt(latest_session.completed_at, 'R'),
                    inline=True
                )
            
            if latest_session.reviewed_at:
                embed.add_field(
                    name="Reviewed",
                    value=discord.utils.format_dt(latest_session.reviewed_at, 'R'),
                    inline=True
                )
            
            # Show answers if in progress or completed
            if latest_session.state in ['in_progress', 'completed'] and latest_session.answers:
                answers_text = []
                for qid, answer in list(latest_session.answers.items())[:3]:  # Show first 3
                    answers_text.append(f"**{qid}**: {str(answer)[:50]}{'...' if len(str(answer)) > 50 else ''}")
                
                if answers_text:
                    embed.add_field(
                        name="Your Answers",
                        value="\n".join(answers_text),
                        inline=False
                    )
                    
                    if len(latest_session.answers) > 3:
                        embed.add_field(
                            name="",
                            value=f"...and {len(latest_session.answers) - 3} more answers",
                            inline=False
                        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="onboarding_questions", description="View onboarding questions (Admin only)")
    @app_commands.describe(show_all="Show all questions including inactive ones")
    async def view_questions(self, interaction: discord.Interaction, show_all: bool = False):
        """View onboarding questions configured for this server."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "view onboarding questions",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        async with get_session() as session:
            query = select(OnboardingQuestion).where(OnboardingQuestion.guild_id == interaction.guild_id)
            if not show_all:
                query = query.where(OnboardingQuestion.is_active == True)
            
            result = await session.execute(query.order_by(OnboardingQuestion.position))
            questions = result.scalars().all()
        
        if not questions:
            embed = discord.Embed(
                title="❓ Onboarding Questions",
                description="No onboarding questions configured. Use the Admin Dashboard to add some!",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="❓ Onboarding Questions",
                description=f"Showing {'all' if show_all else 'active'} questions",
                color=discord.Color.blue()
            )
            
            for question in questions[:10]:  # Limit to 10 questions to avoid embed limits
                status_emoji = "✅" if question.is_active else "❌"
                required_text = " (Required)" if question.required else " (Optional)"
                
                field_value = f"**Type:** {question.type}\n**Position:** {question.position}"
                if question.options:
                    options_preview = ", ".join(question.options[:3])
                    if len(question.options) > 3:
                        options_preview += f" (+{len(question.options) - 3} more)"
                    field_value += f"\n**Options:** {options_preview}"
                
                embed.add_field(
                    name=f"{status_emoji} {question.qid}{required_text}",
                    value=field_value,
                    inline=False
                )
            
            if len(questions) > 10:
                embed.add_field(
                    name="",
                    value=f"...and {len(questions) - 10} more questions",
                    inline=False
                )
        
        embed.set_footer(text="Use the Admin Dashboard to manage questions")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member joins."""
        if member.bot:
            return
        
        # Check if onboarding is configured
        async with get_session() as session:
            result = await session.execute(
                select(OnboardingQuestion)
                .where(
                    and_(
                        OnboardingQuestion.guild_id == member.guild.id,
                        OnboardingQuestion.is_active == True
                    )
                )
                .limit(1)
            )
            has_questions = result.scalar_one_or_none() is not None
        
        if not has_questions:
            return  # No onboarding configured
        
        # Send welcome DM with onboarding instructions
        try:
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=(
                    f"Hi {member.mention}! Welcome to our community.\n\n"
                    "To get started, please complete our onboarding process. "
                    "This will help us assign you the right roles and get you connected with the community."
                ),
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="How to Start",
                value=(
                    "1. Go to any channel in the server\n"
                    "2. Use the `/onboarding` command\n"
                    "3. Follow the prompts to complete your profile\n"
                    "4. Wait for approval from our team"
                ),
                inline=False
            )
            
            embed.add_field(
                name="Need Help?",
                value="If you have any questions, feel free to ask our moderators!",
                inline=False
            )
            
            embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
            embed.set_footer(text=f"Welcome to {member.guild.name}")
            
            await member.send(embed=embed)
            
        except discord.Forbidden:
            # User has DMs disabled, post in welcome channel instead
            guild_config = await self.bot.get_guild_config(member.guild.id)
            if guild_config and guild_config.welcome_channel_id:
                welcome_channel = self.bot.get_channel(guild_config.welcome_channel_id)
                if welcome_channel:
                    from views.onboarding import WelcomeView
                    
                    embed = discord.Embed(
                        title=f"Welcome {member.display_name}!",
                        description=f"Please complete our onboarding process to get started.",
                        color=discord.Color.green()
                    )
                    
                    try:
                        await welcome_channel.send(f"{member.mention}", embed=embed, view=WelcomeView())
                    except discord.Forbidden:
                        pass  # Can't send to welcome channel either
    
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle command errors."""
        if isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏱️ Command Cooldown",
                description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while processing your command.",
                color=discord.Color.red()
            )
            
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(OnboardingCog(bot))