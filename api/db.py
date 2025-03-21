import psycopg2
from psycopg2.extras import DictCursor
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = True  # Automatically commit changes
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        raise

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
    except Exception as e:
        print(f"Error getting next unlabeled QnA: {e}")
        raise
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
    except Exception as e:
        print(f"Error labeling QnA: {e}")
        raise
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
    except Exception as e:
        print(f"Error getting user stats: {e}")
        raise
    finally:
        cur.close()
        conn.close()