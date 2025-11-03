from flask import Blueprint, render_template, request, jsonify,redirect,url_for, make_response
from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask import flash
from src.utils.seo import meta_tags
from src.route.admin_route.admin import (
    render_blog_list_page,
    render_blog_detail_page,
    track_blog_read,
)


from src.models.database import db, Lead, Post

home_bp = Blueprint('home', __name__, url_prefix='/')


@home_bp.route('/')
def homepage():
    meta = meta_tags(
        title="Vertikal Agent – AI Agents for Every Business",
        description="Automate your business operations with Vertikal’s AI Agents for sales, support, and workflows.",
    )
    return render_template('home.html', meta=meta)


@home_bp.route('/solution-core-agent')
def solution_core_agent():
    meta = meta_tags(
        title="Core AI Agent – Vertikal Agent",
        description="The core AI Agent that powers automation across your entire business – from sales to service.",
    )
    return render_template('solution-core-agent.html', meta=meta)


@home_bp.route('/solution-workflow-integration')
def solution_workflow_integration():
    meta = meta_tags(
        title="Workflow Integration Agent – Vertikal Agent",
        description="Integrate your business workflows and automate processes using Vertikal AI workflow agents.",
    )
    return render_template('solution-workflow-integration.html', meta=meta)


@home_bp.route('/solution-voice-agent')
def solution_voice_agent():
    meta = meta_tags(
        title="Voice Agent – Vertikal Agent",
        description="Create natural, human-like voice AI agents for customer service, sales, and support calls.",
    )
    return render_template('solution-voice-agent.html', meta=meta)


@home_bp.route('/solution-custom-agent')
def solution_custom_agent():
    meta = meta_tags(
        title="Custom AI Agent – Vertikal Agent",
        description="Build a custom AI agent tailored for your specific business needs using Vertikal’s framework.",
    )
    return render_template('solution-custom-agent.html', meta=meta)


@home_bp.route('/solution-conversational-agent')
def solution_conversational_agent():
    meta = meta_tags(
        title="Conversational Dashboard – Vertikal Agent",
        description="Manage conversations, analyze engagement, and monitor your AI agents in real-time.",
    )
    return render_template('solution-conversational-dashboard.html', meta=meta)


@home_bp.route('/about')
def about_page():
    meta = meta_tags(
        title="About Vertikal Agent",
        description="Learn how Vertikal Agent is redefining automation through AI agents that think, talk, and act.",
    )
    return render_template('about.html', meta=meta)


@home_bp.route('/contact-us')
def contact_us():
    meta = meta_tags(
        title="Contact Vertikal Agent",
        description="Let’s discuss how Vertikal Agent can help your business scale through automation.",
    )
    return render_template('contact-us.html', meta=meta)


@home_bp.route('/privacy')
def privacy_policy():
    meta = meta_tags(title="Privacy Policy – Vertikal Agent", description="Read Vertikal Agent’s privacy policy.")
    return render_template('privacy.html', meta=meta)


@home_bp.route('/terms')
def terms_of_service():
    meta = meta_tags(title="Terms of Service – Vertikal Agent", description="View Vertikal Agent’s terms of service.")
    return render_template('terms.html', meta=meta)


@home_bp.route('/security')
def security_overview():
    meta = meta_tags(title="Security Overview – Vertikal Agent", description="See how Vertikal Agent keeps your data safe and secure.")
    return render_template('security.html', meta=meta)


@home_bp.route('/robots.txt')
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {url_for('home.sitemap_xml', _external=True)}",
    ]
    response = make_response("\n".join(lines))
    response.headers["Content-Type"] = "text/plain"
    return response


@home_bp.route('/sitemap.xml')
def sitemap_xml():
    pages = []
    ten_days_ago = (datetime.utcnow()).date().isoformat()
    routes = [
        ('home.homepage', {}),
        ('home.about_page', {}),
        ('home.solution_core_agent', {}),
        ('home.solution_workflow_integration', {}),
        ('home.solution_conversational_agent', {}),
        ('home.solution_custom_agent', {}),
        ('home.solution_voice_agent', {}),
        ('home.contact_us', {}),
        ('home.privacy_policy', {}),
        ('home.terms_of_service', {}),
        ('home.security_overview', {}),
        ('home.blog_listing', {}),
    ]
    for endpoint, params in routes:
        pages.append({
            "loc": url_for(endpoint, _external=True, **params),
            "lastmod": ten_days_ago,
        })

    posts = Post.query.filter_by(is_published=True).order_by(Post.updated_at.desc(), Post.created_at.desc()).all()
    for post in posts:
        lastmod_dt = post.updated_at or post.created_at or datetime.utcnow()
        pages.append({
            "loc": url_for('home.blog_detail_public', slug=post.slug, _external=True),
            "lastmod": lastmod_dt.date().isoformat(),
        })

    xml_parts = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>",
    ]
    for page in pages:
        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{page['loc']}</loc>")
        xml_parts.append(f"    <lastmod>{page['lastmod']}</lastmod>")
        xml_parts.append("  </url>")
    xml_parts.append("</urlset>")

    response = make_response("\n".join(xml_parts))
    response.headers["Content-Type"] = "application/xml"
    return response


@home_bp.route('/blog')
def blog_listing():
    return render_blog_list_page()


@home_bp.route('/blog/<slug>')
def blog_detail_public(slug):
    return render_blog_detail_page(slug)


@home_bp.route('/blog/<slug>/track', methods=['POST'])
def blog_detail_track_public(slug):
    return track_blog_read(slug)



@home_bp.route('/contact/lead', methods=['POST'])
def create_lead():
    payload = request.form

    name = payload.get("name", "").strip()
    email = payload.get("email", "").strip()
    phone = payload.get("phone", "").strip()

    if not name:
        flash("Name is required.", "error")
        return redirect(url_for("home.index"))

    lead = Lead(
        name=name,
        email=email or None,
        phone=phone or None,
        source="form",
        intent=payload.get("intent"),
        message=payload.get("message")
    )
    db.session.add(lead)
    db.session.commit()


    flash("✅ Your request has been submitted successfully!", "success")
    return redirect(url_for("home.homepage"))
