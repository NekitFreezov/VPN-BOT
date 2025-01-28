import sqlite3

def create_db():
    conn = sqlite3.connect('vpn_subscriptions.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        user_id INTEGER PRIMARY KEY,
        vless_config TEXT,
        shadowsocks_config TEXT,
        expiration_date TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_db()
