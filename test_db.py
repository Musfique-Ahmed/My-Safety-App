import mysql.connector
from mysql.connector import Error

def test_database():
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='mysafety',
            port=3306
        )
        
        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM appuser")
            user_count = cursor.fetchone()[0]
            print(f"✅ Database connected successfully!")
            print(f"✅ Found {user_count} users in database")
            
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"✅ Found {len(tables)} tables in database")
            
            cursor.close()
            connection.close()
            return True
            
    except Error as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_database()