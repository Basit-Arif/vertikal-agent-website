from flask import url_for, request

def meta_tags(title=None, description=None, image=None, keywords=None):
    """
    Returns meta tag data for templates.
    Dynamically builds canonical URLs and sets defaults if not provided.
    """
    default_title = "Vertikal Agent – AI Agents for Every Business"
    default_description = (
        "Vertikal Agent helps businesses automate sales, support, and operations "
        "with AI-powered voice and chat agents tailored for every industry."
    )
    default_image = url_for('static', filename='images/logo.jpeg', _external=True)
    default_keywords = "AI Agent, Automation, Chatbot, WhatsApp Bot, Business Automation, Vertikal"

    page_url = request.url

    meta = {
        "title": title or default_title,
        "description": description or default_description,
        "image": image or default_image,
        "keywords": keywords or default_keywords,
        "url": page_url,
    }
    return meta