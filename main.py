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
        repo = payload.get('repository', {})
        
        repo_name = repo.get('name', 'Unknown')
        repo_full_name = repo.get('full_name', 'Unknown')
        pr_number = pr.get('number', 0)
        pr_title = pr.get('title', 'No title')
        pr_url = pr.get('html_url', '')
        pr_author = pr.get('user', {}).get('login', 'Unknown')
        pr_state = pr.get('state', '')
        merged = pr.get('merged', False)
        pr_body = pr.get('body', '').strip()
        
        # Additional PR info
        additions = pr.get('additions', 0)
        deletions = pr.get('deletions', 0)
        changed_files = pr.get('changed_files', 0)
        commits_count = pr.get('commits', 0)
        comments_count = pr.get('comments', 0)
        review_comments_count = pr.get('review_comments', 0)
        requested_reviewers = pr.get('requested_reviewers', [])
        reviewers_count = len(requested_reviewers)
        
        base_branch = pr.get('base', {}).get('ref', 'main')
        head_branch = pr.get('head', {}).get('ref', 'unknown')
        
        # Truncate description if too long
        if pr_body:
            if len(pr_body) > 200:
                pr_body = pr_body[:200] + "..."
        
        # Format message based on action
        if action == 'opened':
            icon = "🆕"
            message = (
                f"{icon} <b>Pull Request | {repo_full_name} #{pr_number}</b>\n"
                f"<b>+{additions}</b> <b>-{deletions}</b>\n\n"
                f"<b>{pr_title}</b>\n\n"
            )
            if pr_body:
                message += f"{pr_body}\n\n"
            message += (
                f"👤 <b>{pr_author}</b> wants to merge {commits_count} commit(s) from "
                f"<code>{head_branch}</code> into <code>{base_branch}</code>\n\n"
                f"📊 {reviewers_count} Reviewers • {comments_count + review_comments_count} Comments • "
                f"{changed_files} Files changed\n\n"
                f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
            )
        
        elif action == 'closed':
            if merged:
                icon = "✅"
                message = (
                    f"{icon} <b>Merged | {repo_full_name} #{pr_number}</b>\n"
                    f"<b>+{additions}</b> <b>-{deletions}</b>\n\n"
                    f"<b>{pr_title}</b>\n\n"
                )
                if pr_body:
                    message += f"{pr_body}\n\n"
                message += (
                    f"👤 <b>{sender.get('login', 'Unknown')}</b> merged {commits_count} commit(s) from "
                    f"<code>{head_branch}</code> into <code>{base_branch}</code>\n\n"
                    f"📊 {changed_files} Files changed\n\n"
                    f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
                )
            else:
                icon = "❌"
                message = (
                    f"{icon} <b>Closed | {repo_full_name} #{pr_number}</b>\n\n"
                    f"<b>{pr_title}</b>\n\n"
                )
                if pr_body:
                    message += f"{pr_body}\n\n"
                message += (
                    f"👤 <b>{sender.get('login', 'Unknown')}</b> closed this pull request\n\n"
                    f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
                )
        
        elif action == 'reopened':
            icon = "🔄"
            message = (
                f"{icon} <b>Reopened | {repo_full_name} #{pr_number}</b>\n\n"
                f"<b>{pr_title}</b>\n\n"
            )
            if pr_body:
                message += f"{pr_body}\n\n"
            message += (
                f"👤 <b>{sender.get('login', 'Unknown')}</b> reopened this pull request\n\n"
                f"📊 {reviewers_count} Reviewers • {comments_count + review_comments_count} Comments • "
                f"{changed_files} Files changed\n\n"
                f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
            )
        
        elif action == 'ready_for_review':
            icon = "👀"
            message = (
                f"{icon} <b>Ready for Review | {repo_full_name} #{pr_number}</b>\n"
                f"<b>+{additions}</b> <b>-{deletions}</b>\n\n"
                f"<b>{pr_title}</b>\n\n"
            )
            if pr_body:
                message += f"{pr_body}\n\n"
            message += (
                f"👤 <b>{pr_author}</b> wants to merge {commits_count} commit(s) from "
                f"<code>{head_branch}</code> into <code>{base_branch}</code>\n\n"
                f"📊 {reviewers_count} Reviewers • {comments_count + review_comments_count} Comments • "
                f"{changed_files} Files changed\n\n"
                f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
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
        repo = payload.get('repository', {})
        
        if action != 'submitted':
            return jsonify({"status": "ignored"}), 200
        
        repo_name = repo.get('name', 'Unknown')
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
            f"{icon} <b>Review {state_text} | {repo.get('full_name', 'Unknown')} #{pr_number}</b>\n\n"
            f"<b>{pr_title}</b>\n\n"
            f"👤 <b>{reviewer}</b> {state_text.lower()} this pull request\n\n"
            f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
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
        repo = payload.get('repository', {})
        
        repo_name = repo.get('name', 'Unknown')
        pr_number = pr.get('number', 0)
        pr_title = pr.get('title', 'No title')
        pr_url = pr.get('html_url', '')
        commenter = comment.get('user', {}).get('login', 'Unknown')
        comment_body = comment.get('body', '')[:100]  # First 100 chars
        
        message = (
            f"💬 <b>New Comment | {repo.get('full_name', 'Unknown')} #{pr_number}</b>\n\n"
            f"<b>{pr_title}</b>\n\n"
            f"👤 <b>{commenter}</b> commented:\n"
            f"💭 <i>{comment_body}...</i>\n\n"
            f"🔗 <a href=\"{pr_url}\">View Pull Request</a>"
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
