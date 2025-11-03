from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from slugify import slugify
import math

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




class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    role = db.Column(db.String(50), default="author")  # author, reader, admin
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship("Post", backref="author", lazy=True)
    
    # ---- Password Methods ----
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.name}>"

class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    subtitle = db.Column(db.String(255))
    content = db.Column(db.Text, nullable=False)  # Quill HTML / Delta
    cover_image = db.Column(db.String(255))
    excerpt = db.Column(db.String(500))
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    read_time = db.Column(db.Integer, default=3)
    is_published = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)

    # SEO fields
    meta_title = db.Column(db.String(255))
    meta_description = db.Column(db.String(255))
    meta_keywords = db.Column(db.String(255))

    # relationships
    tags = db.relationship("Tag", secondary="post_tags", back_populates="posts")
    views = db.relationship("BlogView", backref="post", lazy=True, cascade="all, delete-orphan")
    
    def __init__(self, title, content, author_id, **kwargs):
        self.title = title
        self.slug = slugify(title)
        self.content = content
        self.author_id = author_id
        self.read_time = self.calculate_read_time(content)
        super().__init__(**kwargs)

    def calculate_read_time(self, text):
        words = len(text.split())
        return math.ceil(words / 200)

    def __repr__(self):
        return f"<Post {self.title}>"



# ---------- TAGS (Like Medium Topics) ----------
class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship("Post", secondary="post_tags", back_populates="tags")

    def __init__(self, name):
        self.name = name
        self.slug = slugify(name)


# Association table: many-to-many between Post & Tag
post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("posts.id")),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id")),
)


class BlogView(db.Model):
    __tablename__ = "blog_views"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    fingerprint = db.Column(db.String(64), index=True)
    ip_address = db.Column(db.String(120))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    device = db.Column(db.String(40))
    user_agent = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    utm_source = db.Column(db.String(120))
    utm_medium = db.Column(db.String(120))
    utm_campaign = db.Column(db.String(120))
    read_duration = db.Column(db.Integer)  # seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



