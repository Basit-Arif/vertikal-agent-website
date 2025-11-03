from flask import Blueprint, render_template, request, jsonify,redirect,url_for, make_response, current_app, session, g
from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask import flash
from src.utils.seo import meta_tags
from src.models.database import Post, Tag, User, BlogView, Lead, Message, VisitorLog
from werkzeug.utils import secure_filename
import os
import uuid
import json
from urllib.request import urlopen, Request
from collections import Counter
from src.models.database import db, Lead
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

import html
import re
from slugify import slugify

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _save_cover_image(file_storage, title):
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None

    ext = os.path.splitext(filename)[1].lower()
    if ext.replace(".", "") not in ALLOWED_IMAGE_EXTENSIONS:
        return None

    upload_root = current_app.config.get(
        "BLOG_COVER_UPLOAD_FOLDER",
        os.path.join(current_app.static_folder, "uploads", "blog_covers"),
    )
    os.makedirs(upload_root, exist_ok=True)

    base_slug = slugify(title) or "vertikal-cover"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    final_name = f"{base_slug}-{timestamp}{ext}"

    file_path = os.path.join(upload_root, final_name)
    file_storage.save(file_path)

    relative_path = os.path.relpath(file_path, current_app.static_folder)
    return f"/static/{relative_path.replace(os.sep, '/')}"


def generate_unique_slug(title, current_post=None):
    base_slug = slugify(title) or f"post-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    slug = base_slug
    counter = 2

    while True:
        existing = Post.query.filter_by(slug=slug).first()
        if not existing or (current_post and existing.id == current_post.id):
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def detect_device(user_agent):
    ua = (user_agent or "").lower()
    if "mobile" in ua:
        return "mobile"
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "desktop"


def get_form_data():
    try:
        return request.form
    except ModuleNotFoundError:
        raw_body = request.get_data(cache=False, as_text=True)
        parsed = parse_qs(raw_body or "")
        return {key: values[-1] if values else "" for key, values in parsed.items()}


def lookup_geo(ip_address):
    if not ip_address:
        return {}
    if ip_address.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.")):
        return {}
    try:
        request = Request(
            f"https://ipapi.co/{ip_address}/json/",
            headers={"User-Agent": "VertikalAgent/1.0 (+https://vertikalagent.com)"},
        )
        with urlopen(request, timeout=3) as response:
            if response.status != 200:
                return {}
            data = json.loads(response.read().decode("utf-8"))
            if data.get("error"):
                return {}
        return {
            "country": data.get("country_name"),
            "city": data.get("city"),
            "region": data.get("region"),
        }
    except Exception:
        return {}


def get_current_admin():
    user_id = session.get("admin_user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def admin_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = get_current_admin()
        if not user:
            flash("Please sign in to access the admin workspace.", "warning")
            next_target = request.full_path.rstrip("?") if request.args else request.path
            return redirect(url_for("admin.login", next=next_target))
        g.current_admin = user
        return view_func(*args, **kwargs)

    return wrapped_view


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_user_id"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        form = request.form or {}
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""

        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("admin.login"))

        user = User.query.filter(User.email.ilike(email)).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for("admin.login"))

        session.permanent = True
        session["admin_user_id"] = user.id
        session["admin_user_name"] = user.name
        session["admin_user_role"] = user.role
        flash(f"Welcome back, {user.name.split()[0]}!", "success")

        next_url = request.args.get("next") or request.form.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)

        return redirect(url_for("admin.dashboard"))

    return render_template("admin_login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("admin_user_id", None)
    session.pop("admin_user_name", None)
    session.pop("admin_user_role", None)
    flash("You have been signed out.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/dashboard")
@admin_login_required
def dashboard():
    admin_user = g.current_admin
    published_posts = Post.query.filter_by(is_published=True).count()
    total_posts = Post.query.count()
    total_users = User.query.count()
    last_post = Post.query.order_by(Post.created_at.desc()).first()

    stats = {
        "total_posts": total_posts,
        "published_posts": published_posts,
        "total_users": total_users,
        "last_post": last_post,
    }

    return render_template(
        "admin_dashboard.html",
        admin=admin_user,
        stats=stats,
    )


@admin_bp.route("/blogs/new", methods=["GET", "POST"])
@admin_login_required
def add_blog():
    if request.method == "POST":
        title = request.form.get("title")
        subtitle = request.form.get("subtitle")
        raw_content = request.form.get("content")  # From Quill editor
        raw_tags = request.form.get("tags", "")
        cover_image_url = request.form.get("cover_image", "").strip()
        cover_upload = request.files.get("cover_upload")
        excerpt_input = request.form.get("excerpt", "")
        meta_title = request.form.get("meta_title", "").strip()
        meta_description = request.form.get("meta_description", "").strip()
        meta_keywords = request.form.get("meta_keywords", "").strip()
        admin_user = getattr(g, "current_admin", None)
        author_id = admin_user.id if admin_user else session.get("admin_user_id", 1)

        if not title or not raw_content:
            flash("Title and content are required!", "danger")
            return redirect(url_for("admin.add_blog"))
        content = html.unescape(raw_content.strip())
        excerpt = excerpt_input.strip()

        cover_image = cover_image_url or None
        if cover_upload and cover_upload.filename:
            saved_cover_path = _save_cover_image(cover_upload, title)
            if not saved_cover_path:
                flash("Unsupported cover image format. Please upload PNG, JPG, JPEG, GIF, or WEBP.", "danger")
                return redirect(url_for("admin.add_blog"))
            cover_image = saved_cover_path

        if not excerpt:
            # Generate a light excerpt from the HTML if none provided
            plain_text = re.sub(r"<[^>]+>", " ", content)
            plain_text = " ".join(plain_text.split())
            excerpt = plain_text[:200]

        if not meta_title:
            meta_title = title
        if not meta_description:
            meta_description = excerpt[:160]

        new_post = Post(
            title=title,
            subtitle=subtitle,
            content=content,
            author_id=author_id,
            is_published=True,
            created_at=datetime.utcnow(),
            cover_image=cover_image,
            excerpt=excerpt,
            meta_title=meta_title,
            meta_description=meta_description,
            meta_keywords=meta_keywords
        )
        new_post.slug = generate_unique_slug(title, new_post)
        tag_objects = []
        if raw_tags:
            seen_slugs = set()
            for candidate in raw_tags.split(","):
                cleaned_name = " ".join(candidate.strip().split())
                if not cleaned_name:
                    continue

                tag_slug = slugify(cleaned_name)
                if not tag_slug or tag_slug in seen_slugs:
                    continue

                tag = Tag.query.filter_by(slug=tag_slug).first()
                if not tag:
                    tag = Tag(name=cleaned_name)
                    tag.slug = tag_slug
                    db.session.add(tag)

                tag_objects.append(tag)
                seen_slugs.add(tag_slug)

        new_post.tags = tag_objects

        db.session.add(new_post)
        db.session.commit()
        flash("Blog added successfully!", "success")
        return redirect(url_for("admin.manage_blogs"))

    return render_template(
        "add_blog.html",
        form_action=url_for("admin.add_blog"),
        submit_label="Publish story",
        page_heading="Draft a new Vertikal story",
        page_subheading="Craft a compelling update, equip it with the right cover, and polish the SEO before publishing.",
        back_url=url_for("admin.dashboard"),
        back_label="Back to dashboard",
        admin=getattr(g, "current_admin", None),
    )


@admin_bp.route("/blogs/manage")
@admin_login_required
def manage_blogs():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    analytics = {}

    for post in posts:
        views = post.views or []
        total_reads = len(views)
        total_duration = sum(view.read_duration or 0 for view in views if view.read_duration)
        avg_read_time = round(total_duration / total_reads, 1) if total_reads else 0
        fingerprints = {view.fingerprint for view in views if view.fingerprint}

        location_counter = Counter()
        for view in views:
            location_key = (view.country or "Unknown", view.city or "")
            location_counter[location_key] += 1

        if location_counter:
            top_location, _ = location_counter.most_common(1)[0]
            country, city = top_location
            top_location_label = f"{city}, {country}" if city else country
        else:
            top_location_label = "—"

        analytics[post.id] = {
            "total_reads": total_reads,
            "unique_readers": len(fingerprints),
            "avg_read_time": avg_read_time,
            "top_location": top_location_label,
        }

    return render_template(
        "admin_blog_manage.html",
        posts=posts,
        admin=g.current_admin,
        analytics=analytics,
    )


@admin_bp.route("/analytics/visitors")
@admin_login_required
def visitor_logs():
    logs = (
        VisitorLog.query.order_by(VisitorLog.created_at.desc())
        .limit(500)
        .all()
    )
    return render_template(
        "admin_visitors.html",
        logs=logs,
        admin=g.current_admin,
    )


@admin_bp.route("/leads")
@admin_login_required
def lead_list():
    leads = Lead.query.order_by(Lead.created_at.desc()).all()
    return render_template(
        "admin_leads.html",
        leads=leads,
        admin=g.current_admin,
    )


@admin_bp.route("/messages")
@admin_login_required
def message_list():
    messages = (
        Message.query.order_by(Message.created_at.desc())
        .limit(500)
        .all()
    )
    return render_template(
        "admin_messages.html",
        messages=messages,
        admin=g.current_admin,
    )


@admin_bp.route("/users")
@admin_login_required
def manage_users():
    admin_user = g.current_admin
    if admin_user.role != "admin":
        flash("You do not have permission to manage users.", "danger")
        return redirect(url_for("admin.dashboard"))

    users = User.query.order_by(User.joined_at.desc()).all()
    return render_template(
        "admin_users.html",
        users=users,
        admin=admin_user,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_login_required
def edit_user(user_id):
    admin_user = g.current_admin
    if admin_user.role != "admin":
        flash("You do not have permission to edit users.", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        form = get_form_data()
        name = (form.get("name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        role = (form.get("role") or user.role).strip().lower()
        password = form.get("password") or ""

        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        existing = User.query.filter(User.email.ilike(email)).first()
        if existing and existing.id != user.id:
            flash("A user with that email already exists.", "danger")
            return redirect(url_for("admin.edit_user", user_id=user.id))

        if role not in {"admin", "editor", "author"}:
            role = user.role

        user.name = name
        user.email = email
        user.role = role

        if password.strip():
            user.set_password(password.strip())

        db.session.commit()
        flash(f"Updated {user.name}.", "success")
        return redirect(url_for("admin.manage_users"))

    return render_template(
        "admin_user_edit.html",
        admin=admin_user,
        user=user,
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_login_required
def delete_user(user_id):
    admin_user = g.current_admin
    if admin_user.role != "admin":
        flash("You do not have permission to delete users.", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User.query.get_or_404(user_id)
    if user.id == admin_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin.manage_users"))

    db.session.delete(user)
    db.session.commit()
    flash(f"Removed {user.name}.", "success")
    return redirect(url_for("admin.manage_users"))


@admin_bp.route("/blogs/<int:post_id>/edit", methods=["GET", "POST"])
@admin_login_required
def edit_blog(post_id):
    post = Post.query.get_or_404(post_id)
    admin_user = g.current_admin

    if request.method == "POST":
        form = get_form_data()
        title = form.get("title")
        subtitle = form.get("subtitle")
        raw_content = form.get("content")
        raw_tags = form.get("tags", "")
        cover_image_url = (form.get("cover_image") or "").strip()
        cover_upload = request.files.get("cover_upload")
        excerpt_input = form.get("excerpt", "")
        meta_title = (form.get("meta_title") or "").strip()
        meta_description = (form.get("meta_description") or "").strip()
        meta_keywords = (form.get("meta_keywords") or "").strip()

        if not title or not raw_content:
            flash("Title and content are required!", "danger")
            return redirect(url_for("admin.edit_blog", post_id=post.id))

        content = html.unescape(raw_content.strip())
        excerpt = excerpt_input.strip()

        cover_image = post.cover_image
        if cover_image_url:
            cover_image = cover_image_url
        elif form.get("cover_image") is not None and not cover_upload:
            cover_image = None
        if cover_upload and cover_upload.filename:
            saved_cover_path = _save_cover_image(cover_upload, title)
            if not saved_cover_path:
                flash("Unsupported cover image format. Please upload PNG, JPG, JPEG, GIF, or WEBP.", "danger")
                return redirect(url_for("admin.edit_blog", post_id=post.id))
            cover_image = saved_cover_path

        if not excerpt:
            plain_text = re.sub(r"<[^>]+>", " ", content)
            plain_text = " ".join(plain_text.split())
            excerpt = plain_text[:200]

        if not meta_title:
            meta_title = title
        if not meta_description:
            meta_description = excerpt[:160]

        if title != post.title:
            post.slug = generate_unique_slug(title, post)

        post.title = title
        post.subtitle = subtitle
        post.content = content
        post.cover_image = cover_image
        post.excerpt = excerpt
        post.meta_title = meta_title
        post.meta_description = meta_description
        post.meta_keywords = meta_keywords
        post.is_published = True

        tag_objects = []
        if raw_tags:
            seen_slugs = set()
            for candidate in raw_tags.split(","):
                cleaned_name = " ".join(candidate.strip().split())
                if not cleaned_name:
                    continue

                tag_slug = slugify(cleaned_name)
                if not tag_slug or tag_slug in seen_slugs:
                    continue

                tag = Tag.query.filter_by(slug=tag_slug).first()
                if not tag:
                    tag = Tag(name=cleaned_name)
                    tag.slug = tag_slug
                    db.session.add(tag)

                tag_objects.append(tag)
                seen_slugs.add(tag_slug)

        post.tags = tag_objects
        post.updated_at = datetime.utcnow()

        db.session.commit()
        flash("Blog updated successfully!", "success")
        return redirect(url_for("admin.manage_blogs"))

    tag_list = ", ".join(tag.name for tag in post.tags) if post.tags else ""

    return render_template(
        "add_blog.html",
        post=post,
        tag_list=tag_list,
        form_action=url_for("admin.edit_blog", post_id=post.id),
        submit_label="Save changes",
        page_heading="Update Vertikal story",
        page_subheading="Refresh your story, adjust the SEO polish, and keep the Vertikal voice sharp.",
        back_url=url_for("admin.manage_blogs"),
        back_label="Back to posts",
        admin=admin_user,
    )


@admin_bp.route("/blogs/<int:post_id>/delete", methods=["POST"])
@admin_login_required
def delete_blog(post_id):
    admin_user = g.current_admin
    if admin_user.role not in {"admin", "editor"}:
        flash("You do not have permission to delete posts.", "danger")
        return redirect(url_for("admin.manage_blogs"))

    post = Post.query.get_or_404(post_id)
    title = post.title
    db.session.delete(post)
    db.session.commit()
    flash(f"Deleted “{title}”.", "success")
    return redirect(url_for("admin.manage_blogs"))


@admin_bp.route("/users/new", methods=["GET", "POST"])
@admin_login_required
def create_user():
    admin_user = g.current_admin

    if admin_user.role != "admin":
        flash("You do not have permission to add new users.", "danger")
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        form = get_form_data()
        name = (form.get("name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        password = form.get("password") or ""
        role = (form.get("role") or "author").strip().lower()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return redirect(url_for("admin.create_user"))

        existing = User.query.filter(User.email.ilike(email)).first()
        if existing:
            flash("A user with that email already exists.", "danger")
            return redirect(url_for("admin.create_user"))

        if role not in {"admin", "editor", "author"}:
            role = "author"

        new_user = User(name=name, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash(f"User {name} added with {role.title()} privileges.", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin_user_new.html", admin=admin_user)


def render_blog_list_page():
    tag_slug = request.args.get("tag")
    tags = Tag.query.order_by(Tag.name.asc()).all()

    posts_query = Post.query.filter_by(is_published=True)
    active_tag = None

    if tag_slug:
        active_tag = next((tag for tag in tags if tag.slug == tag_slug), None)
        if active_tag:
            posts_query = posts_query.join(Post.tags).filter(Tag.id == active_tag.id)
        else:
            return render_template(
                "blog_list.html",
                posts=[],
                tags=tags,
                active_tag=None,
                requested_tag=tag_slug,
            )

    posts = posts_query.order_by(Post.created_at.desc()).all()
    return render_template(
        "blog_list.html",
        posts=posts,
        tags=tags,
        active_tag=active_tag,
        requested_tag=tag_slug,
    )


# --- VIEW ALL BLOGS ---
@admin_bp.route("/blog")
def all_blogs():
    return render_blog_list_page()


def render_blog_detail_page(slug):
    post = Post.query.filter_by(slug=slug, is_published=True).first_or_404()
    post.view_count += 1

    fingerprint = request.cookies.get("reader_id")
    new_cookie = False
    if not fingerprint:
        fingerprint = uuid.uuid4().hex
        new_cookie = True

    ip_header = request.headers.get("X-Forwarded-For", request.remote_addr)
    ip_address = (ip_header or "").split(",")[0].strip()
    if not ip_address or ip_address.lower() == "unknown":
        ip_address = request.remote_addr
    geo = lookup_geo(ip_address)
    user_agent = request.headers.get("User-Agent")
    device = detect_device(user_agent)

    view = BlogView(
        post=post,
        fingerprint=fingerprint,
        ip_address=ip_address,
        country=geo.get("country"),
        city=geo.get("city"),
        region=geo.get("region"),
        device=device,
        user_agent=user_agent,
        referrer=request.referrer,
        utm_source=request.args.get("utm_source"),
        utm_medium=request.args.get("utm_medium"),
        utm_campaign=request.args.get("utm_campaign"),
    )

    db.session.add(view)
    db.session.commit()

    response = make_response(
        render_template(
            "blog_detail.html",
            post=post,
            view_id=view.id,
            reader_fingerprint=fingerprint,
        )
    )
    if new_cookie:
        response.set_cookie("reader_id", fingerprint, max_age=60 * 60 * 24 * 365, httponly=False, samesite="Lax")
    return response


# --- VIEW SINGLE BLOG ---
@admin_bp.route("/blog/<slug>")
def blog_detail(slug):
    return render_blog_detail_page(slug)


@admin_bp.route("/blog/<slug>/track", methods=["POST"])
def track_blog_read(slug):
    post = Post.query.filter_by(slug=slug, is_published=True).first_or_404()
    payload = request.get_json(silent=True) or {}
    view_id = payload.get("view_id")
    read_duration = payload.get("read_duration")

    if not view_id:
        return jsonify({"status": "missing_view_id"}), 400

    view = BlogView.query.filter_by(id=view_id, post_id=post.id).first()
    if not view:
        return jsonify({"status": "view_not_found"}), 404

    updated = False
    if isinstance(read_duration, (int, float)) and read_duration >= 0:
        view.read_duration = int(read_duration)
        updated = True

    scroll_depth = payload.get("scroll_depth")
    if isinstance(scroll_depth, (int, float)):
        # store as referrer for now? better add column. For simplicity ignore but keep future.
        pass

    if updated:
        view.updated_at = datetime.utcnow()
        db.session.commit()

    return jsonify({"status": "ok"})
