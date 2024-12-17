import sqlite3


def get_db_connection():
    conn = sqlite3.connect("dass.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS dass_score (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            answer TEXT NOT NULL,
            depression_score INTEGER NOT NULL,
            anxiety_score INTEGER NOT NULL,
            stress_score INTEGER NOT NULL,
            date_taken TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES students (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS counsellors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT
        )
        """
    )
    cursor.execute(
        """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                counsellor_id INTEGER NOT NULL,
                time TEXT NOT NULL,
                date TEXT NOT NULL,
                reason TEXT,
                status TEXT CHECK(status IN ('pending', 'confirmed', 'cancelled')) DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students (id),
                FOREIGN KEY (counsellor_id) REFERENCES counsellors (id)
            )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT,
            age INTEGER,
            gender TEXT
        )
        """
    )
    conn.commit()
    conn.close()
