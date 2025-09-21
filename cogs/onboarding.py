"""
Onboarding cog for the Guild Management Bot - FIXED VERSION
"""
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_, delete

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
        
        # Create wizard and load questions
        wizard = OnboardingWizard(existing_session.id if existing_session else None)
        await wizard.load_questions(interaction.guild_id)
        
        # Check if there are any questions configured
        if not wizard.questions:
            embed = discord.Embed(
                title="❌ Onboarding Not Configured",
                description="This server doesn't have onboarding questions set up yet. Please contact an administrator.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Load or create session
        await wizard.load_session(interaction.user.id, interaction.guild_id)
        
        # Send initial message and immediately show first question
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # THIS WAS MISSING - Show the current question immediately
        await wizard.show_current_question(interaction)
    
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
                'completed': discord.Color.blue(),
                'approved': discord.Color.green(),
                'denied': discord.Color.red()
            }
            
            status_messages = {
                'in_progress': "🟡 Your onboarding is in progress. Use `/onboarding` to continue.",
                'completed': "🔵 Your onboarding is complete and awaiting review.",
                'approved': "🟢 Your onboarding has been approved! Welcome to the community!",
                'denied': "🔴 Your onboarding was denied. Please contact an administrator for more information."
            }
            
            embed = discord.Embed(
                title="📝 Onboarding Status",
                description=status_messages.get(latest_session.state, "Unknown status"),
                color=status_colors.get(latest_session.state, discord.Color.gray())
            )
            
            embed.add_field(
                name="Session Created",
                value=discord.utils.format_dt(latest_session.created_at, 'F'),
                inline=True
            )
            
            if latest_session.completed_at:
                embed.add_field(
                    name="Completed",
                    value=discord.utils.format_dt(latest_session.completed_at, 'F'),
                    inline=True
                )
            
            if latest_session.processed_at:
                embed.add_field(
                    name="Processed",
                    value=discord.utils.format_dt(latest_session.processed_at, 'F'),
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="onboarding_queue", description="View the onboarding queue (Admin only)")
    async def onboarding_queue_command(self, interaction: discord.Interaction):
        """View the onboarding queue."""
        if not PermissionChecker.is_admin(interaction.user):
            embed = PermissionChecker.get_permission_error_embed(
                "access the onboarding queue",
                "Administrator, Manage Server, or Manage Roles"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        from views.onboarding import OnboardingQueueView
        
        # Create and show the queue
        queue_view = OnboardingQueueView()
        await queue_view.show_queue(interaction)
    
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
            # User has DMs disabled, try to post in welcome channel instead
            try:
                from database import GuildConfig
                
                async with get_session() as session:
                    result = await session.execute(
                        select(GuildConfig).where(GuildConfig.guild_id == member.guild.id)
                    )
                    guild_config = result.scalar_one_or_none()
                
                if guild_config and guild_config.welcome_channel_id:
                    welcome_channel = self.bot.get_channel(guild_config.welcome_channel_id)
                    if welcome_channel:
                        from views.onboarding import WelcomeView
                        
                        embed = discord.Embed(
                            title=f"Welcome {member.display_name}!",
                            description=f"Please complete our onboarding process to get started. Use `/onboarding` to begin!",
                            color=discord.Color.green()
                        )
                        
                        view = WelcomeView()
                        await welcome_channel.send(embed=embed, view=view)
                        
            except Exception as e:
                print(f"Failed to send welcome message: {e}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leaving - clean up onboarding sessions."""
        if member.bot:
            return
        
        # Clean up any incomplete onboarding sessions
        async with get_session() as session:
            await session.execute(
                delete(OnboardingSession)
                .where(
                    and_(
                        OnboardingSession.user_id == member.id,
                        OnboardingSession.guild_id == member.guild.id,
                        OnboardingSession.state == 'in_progress'
                    )
                )
            )
            await session.commit()


async def setup(bot):
    """Set up the onboarding cog."""
    await bot.add_cog(OnboardingCog(bot))