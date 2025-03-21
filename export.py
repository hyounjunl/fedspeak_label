import psycopg2
import csv
import os

DB_PARAMS = {
    'host': '10.8.12.8',
    'port': '5555',
    'database': 'qfind_db',
    'user': 'qfind',
    'password': 'qfind'
}

def export_tables():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    # Export fomc_statements table
    os.makedirs('export', exist_ok=True)
    
    # Get statements data
    cur.execute("SELECT * FROM fomc_statements")
    with open('export/fomc_statements.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([desc[0] for desc in cur.description])  # Write headers
        writer.writerows(cur.fetchall())  # Write data
    
    # Get qna data
    cur.execute("SELECT * FROM fomc_qna")
    with open('export/fomc_qna.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([desc[0] for desc in cur.description])  # Write headers
        writer.writerows(cur.fetchall())  # Write data
    
    print("Export complete! Data saved to export directory.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    export_tables()