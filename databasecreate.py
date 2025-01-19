import sqlite3

def create_database():
    # Connect to (or create) the database
    conn = sqlite3.connect("Claimdatabase2.db")
    cursor = conn.cursor()

    # Create the `persons` table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)

    # Create the `claims` table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            phone_num TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    # Create the `claim_items` table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claim_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            item_desc TEXT NOT NULL,
            price_per_item REAL NOT NULL,
            qty INTEGER NOT NULL,
            value_item REAL NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES claims (claim_id)
        )
    """)

    # Create the `receipts` table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            image_data BLOB NOT NULL,
            FOREIGN KEY (claim_id) REFERENCES claims (claim_id)
        )
    """)

    # Commit changes and close the connection
    conn.commit()
    conn.close()

    print("Database and tables created successfully!")

if __name__ == "__main__":
    create_database()
