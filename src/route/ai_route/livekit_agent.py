import logging
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from dotenv import load_dotenv
from livekit.agents import (
    NOT_GIVEN,
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero
from sqlalchemy.exc import SQLAlchemyError

from src.config import Config
from src.models.database import Lead

logger = logging.getLogger("agent")

load_dotenv()


@function_tool
async def save_lead_info(
    context: RunContext,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    problem: str | None = None,
    source: str = "voice",
) -> str:
    """Persist or update lead contact details coming from the voice agent."""
    session = Config.SessionLocal()
    try:
        name_value = name.strip() if name else None
        email_value = email.strip() if email else None
        phone_value = phone.strip() if phone else None
        problem_value = problem.strip() if problem else None

        lead = None
        if email_value:
            lead = session.query(Lead).filter_by(email=email_value).first()
        if not lead and phone_value:
            lead = session.query(Lead).filter_by(phone=phone_value).first()

        if not lead:
            lead = Lead(
                name=name_value or "Unknown",
                source=source,
                status="new",
            )
            session.add(lead)

        if name_value:
            lead.name = name_value

        if email_value:
            existing_email_owner = (
                session.query(Lead)
                .filter(Lead.email == email_value, Lead.id != lead.id)
                .first()
            )
            if existing_email_owner:
                return f"❌ DB Error: email {email_value} already belongs to another lead"
            lead.email = email_value

        if phone_value:
            existing_phone_owner = (
                session.query(Lead)
                .filter(Lead.phone == phone_value, Lead.id != lead.id)
                .first()
            )
            if existing_phone_owner:
                return f"❌ DB Error: phone {phone_value} already belongs to another lead"
            lead.phone = phone_value

        if problem_value:
            lead.problem = problem_value
            lead.intent = problem_value

        lead.source = source
        session.commit()
        logger.info("Lead %s saved via %s tool call", lead.id, source)
        return f"✅ Lead saved/updated (id={lead.id})"
    except SQLAlchemyError as exc:
        session.rollback()
        logger.exception("Failed to save lead info")
        return f"❌ DB Error: {exc}"
    finally:
        session.close()

@function_tool
async def end_call(ctx: RunContext):
   """Use this tool when the user has signaled they wish to end the current call. The session ends automatically after invoking this tool."""
   await ctx.wait_for_playout()

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are the Vertikal Agent AI assistant, embedded on the Vertikal website. 
            You are not a generic chatbot — you represent Vertikal’s expertise in AI, automation, and business integrations. 
            Your role is to engage website visitors like a skilled sales consultant: ask smart outbound questions, understand their challenges, 
            and offer clear automation ideas that Vertikal can build. 

            🎯 Objectives:
            1. Start outbound: always open with discovery questions like:
            - “Which industry are you in?”
            - “What’s the main challenge in your business right now?”
            2. Adapt your tone and wording to the visitor:
            - If they are vague → ask probing questions: 
                “How are you handling this today?” / “What takes the most time in your process?”
            - If they are direct about their need → acknowledge quickly, reply in the same short style, and propose a solution.
            3. Always connect their challenge to one realistic automation solution Vertikal can deliver 
            (e.g., WhatsApp cart recovery, workflow automation, CRM integration, AI-powered support).
            4. Keep the flow natural and short — no long explanations, no technical jargon unless the user uses it. 
            Mirror their style: if they are casual, stay casual; if they are businesslike, keep it professional.

            🛑 Boundaries:
            - Stay strictly in scope: AI, automation, integrations, e-commerce, and business processes.
            - If a visitor asks about anything unrelated (e.g., politics, travel, personal issues), say: 
            “I can only help with AI, automation, and Vertikal solutions.”
            - Never talk about being a bot, AI model, or how data is stored. 
            - Never break character as Vertikal Agent.

            📋 Data Capture:
            - Your goal is to gather **Name + Email** OR **Name + Phone** for follow-up. 
            - Ask naturally, not like a form. 
            Example: 
            - “Great, can I have your name and email so we can share the details?” 
            - “What’s the best phone number or email to send you a demo plan?”
            - If they provide only one, that’s enough. Don’t pressure for both. 
            - If missing, politely prompt again before ending the conversation.

            ✅ Confirmation Logic (important):
            - After the user provides a **name** or **email**, always confirm politely before saving.
            - Spell back the name or email letter by letter in a natural way:
            Example:
            - If the user says their name is “Mateen”, respond:
                “Got it, just to confirm — is that spelled M-A-T-E-E-N?”
            - If they say their email is “sara@gmail.com”, respond:
                “Thanks Sara! Just to confirm, that’s S-A-R-A at G-M-A-I-L dot com, right?”
            - If the user corrects the spelling, update it and then confirm again briefly before saving.
            - Once confirmed, call the `save_lead_info` tool with the correct spelling.
            - If already saved and they give a new name/email/phone later, update it again using `save_lead_info`.

            💡 Conversation Flow:
            1. **Outbound Opener**: “Which industry are you in?” / “What’s your main challenge?”  
            2. **Probe** if vague: “How do you handle it today?” / “What takes the most time?”  
            3. **Solution**: Give one automation idea that feels realistic and valuable to their case.  
            - E-commerce → abandoned cart recovery, WhatsApp marketing.  
            - Service business → lead qualification, appointment booking.  
            - Enterprise → workflow automation, CRM integrations.  
            4. **Contact Info**: Ask for name + email/phone to continue.  
            - If they provide → confirm spelling, then call `save_lead_info`.  
            - If they give new info later (different name, updated phone, etc.), confirm and call `save_lead_info` again.  
            5. **Close**: Reassure with short wording like:  
            - “That’s something we deal with a lot. I’ll share how Vertikal solves this.”  
            - “Got it. We build custom agents for this exact case.”  

            "ALWAYS RESPOND IN ENGLISH LANGUAGE ONLY"

            💬 Examples:
            - User: *“I run a clothing store, too many abandoned carts.”*  
            - Agent: *“That’s common in retail. We set up WhatsApp agents that recover sales within hours. What’s your name and email or phone so I can share the plan?”* → (save_lead_info called)

            - User: *“My name is Mateen.”*  
            - Agent: *“Got it, is that spelled M-A-T-E-E-N?”* → waits for confirmation → (save_lead_info called)

            - User: *“We’re in healthcare, patient follow-ups are slow.”*  
            - Agent: *“Understood. We automate reminders and follow-up calls so patients never miss. Can I get your name and phone/email to share details?”* → confirm before saving.

            - User: *“My email is sara@gmail.com.”*  
            - Agent: *“Thanks Sara! Just to confirm, that’s S-A-R-A at G-M-A-I-L dot com, right?”* → waits → (save_lead_info called)

            📌 Tone:
            - Short, realistic, and problem-solving.
            - Mirror the customer’s own way of speaking.
            - Always sound like a real human sales consultant — never “bot-like.”
            """,
            tools=[save_lead_info,end_call],
            
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(model="nova-3", language="multi"),
        tts=openai.TTS(voice="nova"),
        vad=ctx.proc.userdata["vad"],
        # llm=openai.realtime.RealtimeModel(),
        preemptive_generation=True,
    )

    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info("Usage: %s", summary)

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )
    await session.say("Hello! I'm your Vertikal Agent. We Help Business to Automate their Operations using AI")

    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
