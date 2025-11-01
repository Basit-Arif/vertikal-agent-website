from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(50), unique=True, nullable=True)
    industry = db.Column(db.String(100))

    problem = db.Column(db.Text)                  # Main description or automation goal
    source = db.Column(db.String(30), nullable=False)   # 'voice', 'text', or 'form'
    intent = db.Column(db.String(100))            # e.g. 'demo request', 'support', 'automation help'
    summary = db.Column(db.Text)                  # Short AI summary of conversation

    form_type = db.Column(db.String(100))         # Only for contact form submissions (e.g. 'Demo Request')
    source_page = db.Column(db.String(200))       # Page where form was submitted
    message = db.Column(db.Text)                  # Initial message entered in form/chat

    # Lead lifecycle tracking
    status = db.Column(
        db.String(30),
        default="new",
        nullable=False
    )
    # Options: 'new', 'in-progress', 'converted', 'lost'

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Lead {self.id}: {self.name or 'Unknown'} | Status={self.status}>"




class Message(db.Model):
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    direction = db.Column(db.String(10), default="inbound")  
    # 'inbound' (from lead) or 'outbound' (from you/system)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to Lead
    lead = db.relationship(
        "Lead",
        backref=db.backref("messages", lazy=True, cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<Message {self.id} ({self.direction}) for Lead {self.lead_id}>"


# ----------------------------
# Interaction Model
# ----------------------------
class Interaction(db.Model):
    __tablename__ = "interaction"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False)

    interaction_type = db.Column(db.String(50), nullable=False)  
    # e.g. 'call', 'email', 'meeting', 'chat'

    notes = db.Column(db.Text)
    outcome = db.Column(db.String(100))  
    # e.g. 'follow-up needed', 'demo scheduled', 'closed - won', 'closed - lost'

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to Lead
    lead = db.relationship(
        "Lead",
        backref=db.backref("interactions", lazy=True, cascade="all, delete-orphan")
    )

    def __repr__(self):
        return f"<Interaction {self.interaction_type} for Lead {self.lead_id}>"
    

class VisitorLog(db.Model):
    __tablename__ = 'visitor_log'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(100))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    path = db.Column(db.String(200))

    utm_source = db.Column(db.String(100))
    utm_medium = db.Column(db.String(100))
    utm_campaign = db.Column(db.String(100))
    utm_term = db.Column(db.String(100))
    utm_content = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

