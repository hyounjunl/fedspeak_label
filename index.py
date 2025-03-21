from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import psycopg2
from psycopg2.extras import DictCursor
import os
import secrets
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))

# Database configuration from environment variables
DB_PARAMS = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def get_db_connection():
    """Create and return a database connection"""
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = True  # Automatically commit changes
    return conn

def get_next_unlabeled_qna():
    """Get the next unlabeled QnA pair"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # Get next unlabeled QnA with statement info
        cur.execute("""
            SELECT q.id, q.questioner, q.question, q.responder, q.response, 
                   s.date, s.filename
            FROM fomc_qna q
            JOIN fomc_statements s ON q.statement_id = s.id
            WHERE q.is_labeled = FALSE
            ORDER BY RANDOM() -- Randomize to distribute workload among users
            LIMIT 1
        """)
        
        row = cur.fetchone()
        result = dict(row) if row else None
        
        # Convert the date to string format if it exists
        if result and 'date' in result:
            result['date'] = result['date'].strftime('%Y-%m-%d')
            
        return result
    finally:
        cur.close()
        conn.close()

def label_qna(qna_id, label_value, user_id):
    """Label a QnA pair and record the user who labeled it"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Update the QnA record with label and user info
        cur.execute("""
            UPDATE fomc_qna
            SET is_labeled = TRUE, 
                label = %s,
                labeled_by = %s,
                labeled_at = NOW()
            WHERE id = %s
        """, (label_value, user_id, qna_id))
        
        # Get the number of remaining unlabeled QnAs
        cur.execute("""
            SELECT COUNT(*) FROM fomc_qna WHERE is_labeled = FALSE
        """)
        remaining = cur.fetchone()[0]
        
        # Get labeling statistics for this user
        cur.execute("""
            SELECT COUNT(*) FROM fomc_qna 
            WHERE labeled_by = %s
        """, (user_id,))
        user_count = cur.fetchone()[0]
        
        return {
            'success': True,
            'remaining': remaining,
            'user_count': user_count
        }
    finally:
        cur.close()
        conn.close()

def get_user_stats(user_id):
    """Get labeling statistics for a user"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get total labeled by this user
        cur.execute("""
            SELECT COUNT(*) FROM fomc_qna 
            WHERE labeled_by = %s
        """, (user_id,))
        total = cur.fetchone()[0]
        
        # Get relevant count
        cur.execute("""
            SELECT COUNT(*) FROM fomc_qna 
            WHERE labeled_by = %s AND label = TRUE
        """, (user_id,))
        relevant = cur.fetchone()[0]
        
        # Get irrelevant count
        cur.execute("""
            SELECT COUNT(*) FROM fomc_qna 
            WHERE labeled_by = %s AND label = FALSE
        """, (user_id,))
        irrelevant = cur.fetchone()[0]
        
        # Get overall stats
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_labeled = TRUE) as labeled,
                COUNT(*) FILTER (WHERE is_labeled = FALSE) as unlabeled
            FROM fomc_qna
        """)
        overall = cur.fetchone()
        
        return {
            'user': {
                'total': total,
                'relevant': relevant,
                'irrelevant': irrelevant
            },
            'overall': {
                'total': overall[0],
                'labeled': overall[1],
                'unlabeled': overall[2]
            }
        }
    finally:
        cur.close()
        conn.close()

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
    stats = get_user_stats(session['user_id'])
    
    return render_template('label.html', 
                          user_id=session['user_id'], 
                          stats=stats)

@app.route('/api/next_qna', methods=['GET'])
def api_next_qna():
    """API to get the next QnA pair"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    next_qna = get_next_unlabeled_qna()
    if next_qna:
        return jsonify(next_qna)
    else:
        return jsonify({'error': 'No more unlabeled QnA pairs available'}), 404

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
    
    result = label_qna(qna_id, label, session['user_id'])
    return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API to get user statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401
    
    stats = get_user_stats(session['user_id'])
    return jsonify(stats)

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

# For local development, use the development server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)