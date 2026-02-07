from flask import Flask, request, jsonify
import requests
import os
import hmac
import hashlib

app = Flask(__name__)

# Telegram config
TELEGRAM_BOT_TOKEN = "8305092853:AAFJEMce0TPjU2NTFcmLqbnlGJaXC-ZeU1Q"
TELEGRAM_CHAT_ID = "-1003773551774"
TELEGRAM_TOPIC_ID = "59"

# GitHub webhook secret (set this in GitHub webhook settings)
GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

def verify_signature(payload_body, signature_header):
    """Verify GitHub webhook signature"""
    if not GITHUB_WEBHOOK_SECRET:
        return True  # Skip verification if secret not set
    
    hash_object = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

def send_telegram_message(text):
    """Send message to Telegram topic"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_TOPIC_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending to Telegram: {e}")
        return False

@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook"""
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    if GITHUB_WEBHOOK_SECRET and not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 403
    
    event_type = request.headers.get('X-GitHub-Event', '')
    payload = request.json
    
    # Handle pull request events
    if event_type == 'pull_request':
        action = payload.get('action', '')
        pr = payload.get('pull_request', {})
        sender = payload.get('sender', {})
        
        pr_number = pr.get('number', 0)
        pr_title = pr.get('title', 'No title')
        pr_url = pr.get('html_url', '')
        pr_author = pr.get('user', {}).get('login', 'Unknown')
        pr_state = pr.get('state', '')
        merged = pr.get('merged', False)
        
        # Format message based on action
        if action == 'opened':
            icon = "🆕"
            message = (
                f"{icon} <b>New Pull Request</b>\n\n"
                f"<b>#{pr_number}</b> {pr_title}\n"
                f"👤 <b>Author:</b> {pr_author}\n"
                f"🔗 <a href=\"{pr_url}\">View PR</a>"
            )
        
        elif action == 'closed':
            if merged:
                icon = "✅"
                message = (
                    f"{icon} <b>Pull Request Merged</b>\n\n"
                    f"<b>#{pr_number}</b> {pr_title}\n"
                    f"👤 <b>Merged by:</b> {sender.get('login', 'Unknown')}\n"
                    f"🔗 <a href=\"{pr_url}\">View PR</a>"
                )
            else:
                icon = "❌"
                message = (
                    f"{icon} <b>Pull Request Closed</b>\n\n"
                    f"<b>#{pr_number}</b> {pr_title}\n"
                    f"👤 <b>Closed by:</b> {sender.get('login', 'Unknown')}\n"
                    f"🔗 <a href=\"{pr_url}\">View PR</a>"
                )
        
        elif action == 'reopened':
            icon = "🔄"
            message = (
                f"{icon} <b>Pull Request Reopened</b>\n\n"
                f"<b>#{pr_number}</b> {pr_title}\n"
                f"👤 <b>Reopened by:</b> {sender.get('login', 'Unknown')}\n"
                f"🔗 <a href=\"{pr_url}\">View PR</a>"
            )
        
        elif action == 'ready_for_review':
            icon = "👀"
            message = (
                f"{icon} <b>Pull Request Ready for Review</b>\n\n"
                f"<b>#{pr_number}</b> {pr_title}\n"
                f"👤 <b>Author:</b> {pr_author}\n"
                f"🔗 <a href=\"{pr_url}\">View PR</a>"
            )
        
        else:
            # Skip other actions
            return jsonify({"status": "ignored"}), 200
        
        send_telegram_message(message)
        return jsonify({"status": "success"}), 200
    
    # Handle pull request review events
    elif event_type == 'pull_request_review':
        action = payload.get('action', '')
        pr = payload.get('pull_request', {})
        review = payload.get('review', {})
        
        if action != 'submitted':
            return jsonify({"status": "ignored"}), 200
        
        pr_number = pr.get('number', 0)
        pr_title = pr.get('title', 'No title')
        pr_url = pr.get('html_url', '')
        reviewer = review.get('user', {}).get('login', 'Unknown')
        review_state = review.get('state', '').lower()
        
        # Format based on review state
        if review_state == 'approved':
            icon = "✅"
            state_text = "Approved"
        elif review_state == 'changes_requested':
            icon = "🔄"
            state_text = "Requested Changes"
        elif review_state == 'commented':
            icon = "💬"
            state_text = "Commented"
        else:
            return jsonify({"status": "ignored"}), 200
        
        message = (
            f"{icon} <b>PR Review: {state_text}</b>\n\n"
            f"<b>#{pr_number}</b> {pr_title}\n"
            f"👤 <b>Reviewer:</b> {reviewer}\n"
            f"🔗 <a href=\"{pr_url}\">View PR</a>"
        )
        
        send_telegram_message(message)
        return jsonify({"status": "success"}), 200
    
    # Handle pull request review comment events
    elif event_type == 'pull_request_review_comment':
        action = payload.get('action', '')
        
        if action != 'created':
            return jsonify({"status": "ignored"}), 200
        
        pr = payload.get('pull_request', {})
        comment = payload.get('comment', {})
        
        pr_number = pr.get('number', 0)
        pr_title = pr.get('title', 'No title')
        pr_url = pr.get('html_url', '')
        commenter = comment.get('user', {}).get('login', 'Unknown')
        comment_body = comment.get('body', '')[:100]  # First 100 chars
        
        message = (
            f"💬 <b>New Review Comment</b>\n\n"
            f"<b>#{pr_number}</b> {pr_title}\n"
            f"👤 <b>By:</b> {commenter}\n"
            f"💭 {comment_body}...\n"
            f"🔗 <a href=\"{pr_url}\">View PR</a>"
        )
        
        send_telegram_message(message)
        return jsonify({"status": "success"}), 200
    
    return jsonify({"status": "event_type_not_supported"}), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
    return jsonify({
        "service": "GitHub PR Webhook Handler",
        "status": "running",
        "endpoints": {
            "webhook": "/webhook/github",
            "health": "/health"
        }
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
