import os
from typing import Optional
from dataclasses import dataclass, asdict
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from openai import OpenAI
from sqlalchemy.exc import SQLAlchemyError
from src.models.database import db, Lead, Message
from agents import Agent, Runner, function_tool
import asyncio
from agents import OpenAIConversationsSession




agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")

DEFAULT_SYSTEM_PROMPT = """
You are the Vertikal Agent AI assistant, embedded on the Vertikal website. 
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
- ✅ Whenever you get a name, email, phone, or problem → **call the `save_lead_info` tool** to save it.
- ✅ If this information was already collected but the user provides a new value, **update the saved info** by calling the tool again.

💡 Conversation Flow:
1. **Outbound Opener**: “Which industry are you in?” / “What’s your main challenge?”  
2. **Probe** if vague: “How do you handle it today?” / “What takes the most time?”  
3. **Solution**: Give one automation idea that feels realistic and valuable to their case.  
   - E-commerce → abandoned cart recovery, WhatsApp marketing.  
   - Service business → lead qualification, appointment booking.  
   - Enterprise → workflow automation, CRM integrations.  
4. **Contact Info**: Ask for name + email/phone to continue.  
   - If they provide → call `save_lead_info`.  
   - If they give new info later (different name, updated phone, etc.), call `save_lead_info` again with updated fields.  
5. **Close**: Reassure with short wording like:  
   - “That’s something we deal with a lot. I’ll share how Vertikal solves this.”  
   - “Got it. We build custom agents for this exact case.”  

💬 Examples:
- User: *“I run a clothing store, too many abandoned carts.”*  
- Agent: *“That’s common in retail. We set up WhatsApp agents that recover sales within hours. What’s your name and email or phone so I can share the plan?”* → (save_lead_info called)

- User: *“We’re in healthcare, patient follow-ups are slow.”*  
- Agent: *“Understood. We automate reminders and follow-up calls so patients never miss. Can I get your name and phone/email to share details?”* → (save_lead_info called)

- User: *“My name is Sara, I use a different phone now: 123456.”*  
- Agent: *“Thanks Sara, I’ve noted your new number so we can stay in touch.”* → (save_lead_info called with updated phone)

📌 Tone:
- Short, realistic, and problem-solving.
- Mirror the customer’s own way of speaking.
- Always sound like a real human sales consultant — never “bot-like.”
"""

# ----------------------------
# Utilities
# ----------------------------
def _sanitize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = value.strip()
    return cleaned or None


def _get_openai_client() -> OpenAI:
    api_key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")
    return OpenAI(api_key=api_key)


def _resolve_system_prompt() -> str:
    return current_app.config.get("OPENAI_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT


def _resolve_model() -> str:
    return current_app.config.get("OPENAI_AGENT_MODEL", "gpt-4o-mini")

from flask import session as flask_session

# ----------------------------
# Get or Create Session
# ----------------------------
def get_or_create_session(user_identifier: Optional[str] = None):
    """
    Either reuse an existing conversation session (if provided),
    or create a new one with unique session_id.
    """
    if not user_identifier:
        # Check if stored in Flask session
        user_identifier = flask_session.get("conversation_id")

    if not user_identifier:
        # If no existing session, create new
        user_identifier = str(uuid4())
        flask_session["conversation_id"] = user_identifier

    # Create SQLite-backed session (per-user conversation history)
    return SQLiteSession(user_identifier, "conversations.db")


# ----------------------------
# State Schema
# ----------------------------
@dataclass
class Contact_Info:
    name: Optional[str] = None
    email: Optional[str] = None
    phonenumber: Optional[str] = None
    problem: Optional[str] = None


# ----------------------------
# Tool Function
# ----------------------------
@function_tool(
    name_override="save_lead_info",
    description_override="Save or update a lead's name, email, phone, or problem from the chat."
)
def save_lead_info(
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    problem: Optional[str] = None,
    source: str = "chat"
) -> str:
    """
    Save or update a lead record in the database.
    Upgrades Unknown or missing fields if new info is available.
    """
    try:
        lead = None
        if email:
            lead = Lead.query.filter_by(email=email).first()
        elif phone:
            lead = Lead.query.filter_by(phone=phone).first()

        if not lead:
            # fallback: try by id or just create
            lead = Lead(name="Unknown", source=source, status="new")
            db.session.add(lead)

        # 🔹 Upgrade logic
        if name and (not lead.name or lead.name.lower() == "unknown"):
            lead.name = name.strip()

        if email and (not lead.email):
            lead.email = email.strip()

        if phone and (not lead.phone):
            lead.phone = phone.strip()

        if problem:
            lead.intent = problem.strip()

        lead.source = source
        db.session.add(lead)

        db.session.commit()
        return f"✅ Lead saved/updated (id={lead.id})"

    except SQLAlchemyError as e:
        db.session.rollback()
        return f"❌ DB Error: {str(e)}"
agent = Agent(
    name="Agent",
    instructions=DEFAULT_SYSTEM_PROMPT,   
    tools=[save_lead_info],  
)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
from openai import AsyncOpenAI

from agents import SQLiteSession
session = SQLiteSession("user_124", "conversations.db")



from flask import Response, stream_with_context
import json
from openai.types.responses import ResponseTextDeltaEvent



@agent_bp.route("/chat", methods=["POST"])
def chatting():
    data = request.get_json() or {}
    user_msg = (data.get("message") or "").strip()
    user_identifier = data.get("session_id")

    if not user_msg:
        return jsonify({"error": "message is required"}), 400

    try:
        # 🔹 Find or create a lead
        lead = Lead.query.filter_by(id=user_identifier).first()
        if not lead:
            lead = Lead(
                id=user_identifier,
                name="Unknown",   # avoid NULL constraint errors
                source="chat",
                status="new"
            )
            db.session.add(lead)
            db.session.commit()

        # ✅ Store lead.id separately to avoid DetachedInstanceError
        lead_id = lead.id

        # ✅ Save inbound (user) message immediately
        inbound = Message(
            lead_id=lead_id,
            content=user_msg,
            direction="inbound"
        )
        db.session.add(inbound)
        db.session.commit()

        # 🔹 Maintain agent session
        session = get_or_create_session(user_identifier)

        async def agen():
            """Async generator to stream agent response"""
            result_stream = Runner.run_streamed(agent, user_msg, session=session)
            async for event in result_stream.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    yield event.data.delta
                elif event.type == "response.completed":  # ✅ explicit end
                    yield "[[END]]"
        def generate():
            """Bridge async generator to sync Flask response"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            agen_iter = agen()

            reply_accumulator = ""  # buffer agent reply

            while True:
                try:
                    chunk = loop.run_until_complete(agen_iter.__anext__())
                    if chunk == "[[END]]":
                        # ✅ Save outbound (agent) message once completed
                        if reply_accumulator.strip():
                            outbound = Message(
                                lead_id=lead_id,
                                content=reply_accumulator.strip(),
                                direction="outbound"
                            )
                            db.session.add(outbound)
                            db.session.commit()
                        break

                    reply_accumulator += chunk
                    yield chunk  # stream to client

                except StopAsyncIteration:
                    break

        return Response(stream_with_context(generate()), mimetype="text/plain")

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Agent failed: {str(e)}"}), 500
    
from livekit import api
import uuid

@agent_bp.route('/getToken')
def getToken():
  unique_room_name = f"vertikal-room-{uuid.uuid4().hex[:8]}"
  token = api.AccessToken(os.getenv('LIVEKIT_API_KEY'), os.getenv('LIVEKIT_API_SECRET')) \
    .with_identity("identity") \
    .with_name("my_name") \
    .with_grants(api.VideoGrants(
        room_join=True,
        room=unique_room_name,
    ))
  return token.to_jwt()