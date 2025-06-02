import sys
import json
import os
import bcrypt

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

def add_user(username, password):
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    else:
        users = {}
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = hashed
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)
    print(f"User '{username}' added/updated.")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <username> <password>")
        sys.exit(1)
    username = sys.argv[1]
    password = sys.argv[2]
    add_user(username, password) 