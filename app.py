from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import os
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__, template_folder='../templates')
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Import database functions
from api.db import get_next_unlabeled_qna, label_qna, get_user_stats

# Routes
@app.route('/')
def index():
    """Main page - user identification"""
    return render_template('index.html')

@app.route('/label', methods=['GET', 'POST'])
def label():
    """Labeling page"""
    # Check if user is set
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    # Get user's labeling statistics
    try:
        stats = get_user_stats(session['user_id'])
    except Exception as e:
        print(f"Error getting stats: {e}")
        stats = {
            'user': {'total': 0, 'relevant': 0, 'irrelevant': 0},
            'overall': {'total': 0, 'labeled': 0, 'unlabeled': 0}
        }
    
    return render_template('label.html', 
                          user_id=session['user_id'], 
                          stats=stats)

@app.route('/api/next_qna', methods=['GET'])
def api_next_qna():
    """API to get the next QnA pair"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        next_qna = get_next_unlabeled_qna()
        if next_qna:
            return jsonify(next_qna)
        else:
            return jsonify({'error': 'No more unlabeled QnA pairs available'}), 404
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/label_qna', methods=['POST'])
def api_label_qna():
    """API to label a QnA pair"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    data = request.json
    qna_id = data.get('qna_id')
    label = data.get('label')
    
    if not qna_id or label is None:
        return jsonify({'error': 'Missing qna_id or label'}), 400
    
    try:
        result = label_qna(qna_id, label, session['user_id'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API to get user statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    try:
        stats = get_user_stats(session['user_id'])
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/set_user', methods=['POST'])
def set_user():
    """Set the user ID in the session"""
    user_id = request.form.get('user_id')
    if user_id:
        session['user_id'] = user_id
        return redirect(url_for('label'))
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Log out the user"""
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint for Vercel"""
    return jsonify({"status": "ok"})

# This is important for Vercel
app.debug = False