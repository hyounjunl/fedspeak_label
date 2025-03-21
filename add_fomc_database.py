import os
import json
import psycopg2
from psycopg2.extras import execute_values
import datetime

# Database configuration
DB_PARAMS = {
    'host': '10.8.12.8',
    'port': '5555',
    'database': 'qfind_db',
    'user': 'qfind',
    'password': 'qfind'
}

def create_tables(conn):
    """Create necessary tables if they don't exist"""
    with conn.cursor() as cur:
        # Create table for FOMC statements
        cur.execute("""
        CREATE TABLE IF NOT EXISTS fomc_statements (
            id SERIAL PRIMARY KEY,
            date DATE NOT NULL,
            filename VARCHAR(255) NOT NULL,
            speaker VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create table for QnA pairs
        cur.execute("""
        CREATE TABLE IF NOT EXISTS fomc_qna (
            id SERIAL PRIMARY KEY,
            statement_id INTEGER REFERENCES fomc_statements(id),
            questioner VARCHAR(255) NOT NULL,
            question TEXT NOT NULL,
            responder VARCHAR(255) NOT NULL,
            response TEXT NOT NULL,
            is_labeled BOOLEAN DEFAULT FALSE,
            label BOOLEAN DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        conn.commit()

def extract_date_from_filename(filename):
    """Extract date from FOMC filename format like FOMCpresconf20180613.json"""
    # Extract the date string (assume format is consistent)
    date_str = filename.split('FOMCpresconf')[1].split('.')[0]
    # Convert to datetime object (format: YYYYMMDD)
    return datetime.datetime.strptime(date_str, '%Y%m%d').date()

def process_json_files(directory_path, conn):
    """Process all JSON files in the given directory"""
    for filename in os.listdir(directory_path):
        if filename.endswith('.json'):
            file_path = os.path.join(directory_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract date from filename
                date = extract_date_from_filename(filename)
                
                # Process the file
                insert_data(conn, data, filename, date)
                print(f"Successfully processed {filename}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")
                continue

def insert_data(conn, data, filename, date):
    """Insert data from a JSON file into the database"""
    try:
        with conn.cursor() as cur:
            # Check if 'statement' key exists and is not empty
            if 'statement' not in data or not data['statement']:
                print(f"Warning: No statement found in {filename}")
                return
                
            # Get statement speaker and content safely
            try:
                statement_speaker = list(data['statement'].keys())[0]
                statement_content = data['statement'][statement_speaker]
            except (IndexError, KeyError) as e:
                print(f"Error extracting statement from {filename}: {e}")
                print(f"Statement structure: {data['statement']}")
                return
            
            # Check if this file has already been processed
            cur.execute("""
            SELECT id FROM fomc_statements WHERE filename = %s
            """, (filename,))
            
            existing_record = cur.fetchone()
            if existing_record:
                print(f"File {filename} already exists in database, skipping.")
                return
            
            # Insert statement
            cur.execute("""
            INSERT INTO fomc_statements (date, filename, speaker, content)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """, (date, filename, statement_speaker, statement_content))
            
            statement_id = cur.fetchone()[0]
            
            # Insert QnA pairs
            if 'qna' in data and data['qna']:
                qna_records = []
                for i, qna in enumerate(data['qna']):
                    try:
                        # Check if question and response keys exist
                        if 'question' not in qna or 'response' not in qna:
                            print(f"Warning: Missing question or response in {filename}, QnA #{i+1}")
                            continue
                            
                        # Try to extract data safely
                        if not qna['question'] or not qna['response']:
                            print(f"Warning: Empty question or response in {filename}, QnA #{i+1}")
                            continue
                            
                        questioner = list(qna['question'].keys())[0]
                        question = qna['question'][questioner]
                        responder = list(qna['response'].keys())[0]
                        response = qna['response'][responder]
                        
                        qna_records.append((
                            statement_id, questioner, question, responder, response
                        ))
                    except (IndexError, KeyError) as e:
                        print(f"Error processing QnA #{i+1} in {filename}: {e}")
                        print(f"QnA structure: {qna}")
                        continue
                
                # Batch insert for better performance
                if qna_records:
                    print(f"Inserting {len(qna_records)} QnA records for {filename}")
                    execute_values(cur, """
                    INSERT INTO fomc_qna (statement_id, questioner, question, responder, response)
                    VALUES %s
                    """, qna_records)
            
            conn.commit()
            print(f"Successfully inserted {filename} with statement_id {statement_id}")
    except Exception as e:
        conn.rollback()
        print(f"Error inserting data for {filename}: {e}")
        raise

def reset_tables(conn):
    """Drop and recreate tables - use with caution!"""
    try:
        with conn.cursor() as cur:
            # Drop tables in correct order due to foreign key constraints
            cur.execute("DROP TABLE IF EXISTS fomc_qna CASCADE")
            cur.execute("DROP TABLE IF EXISTS fomc_statements CASCADE")
            conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error resetting tables: {e}")
        return False

def main():
    # Connect to the database
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        print("Connected to the database successfully!")
        
        # Ask to reset tables
        reset = input("Do you want to reset all tables and reimport everything? (yes/no): ").strip().lower()
        if reset in ['yes', 'y']:
            if reset_tables(conn):
                print("Tables reset successfully.")
            else:
                print("Failed to reset tables. Exiting.")
                return
        
        # Create tables
        create_tables(conn)
        print("Tables created or already exist.")
        
        # Process directory with Powell's JSON files
        directory_path = './Powell'
        process_json_files(directory_path, conn)
        print(f"Processed all JSON files in {directory_path}")
        
        # Close connection
        conn.close()
        print("Database connection closed.")
        
    except psycopg2.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()