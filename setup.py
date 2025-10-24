#!/usr/bin/env python3
"""
Setup script for Infrastructure Provisioning Agent
Initializes the project with necessary configuration and dependencies
"""
import os
import sys
import subprocess
from pathlib import Path
from cryptography.fernet import Fernet

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def check_python_version():
    """Ensure Python 3.11+ is being used"""
    if sys.version_info < (3, 11):
        print("❌ Error: Python 3.11 or higher is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")

def check_terraform():
    """Check if Terraform is installed"""
    try:
        result = subprocess.run(['terraform', '--version'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✅ {version}")
            return True
    except FileNotFoundError:
        print("❌ Terraform not found")
        print("   Install from: https://www.terraform.io/downloads")
        return False

def check_postgresql():
    """Check if PostgreSQL is installed"""
    try:
        result = subprocess.run(['psql', '--version'],
                              capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✅ {version}")
            return True
    except FileNotFoundError:
        print("⚠️  PostgreSQL not found (optional for local development)")
        return False

def create_env_file():
    """Create .env file with generated secrets"""
    print_header("Creating Environment Configuration")

    env_file = Path('.env')

    if env_file.exists():
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("   Skipping .env creation")
            return

    # Generate secrets
    secret_key = Fernet.generate_key().decode()
    encryption_key = Fernet.generate_key().decode()

    env_content = f"""# Infrastructure Provisioning Agent Configuration

# Database
DATABASE_URL=postgresql://infraagent:infraagent@localhost:5432/infraagent

# Security Keys (DO NOT COMMIT TO VERSION CONTROL!)
SECRET_KEY={secret_key}
ENCRYPTION_KEY={encryption_key}

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# MCP Server
MCP_SERVER_URL=ws://localhost:8001/mcp

# Logging
LOG_LEVEL=INFO
SQL_ECHO=false

# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES=60

# AWS (optional - can be configured per user)
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_DEFAULT_REGION=us-east-1
"""

    with open(env_file, 'w') as f:
        f.write(env_content)

    print("✅ Created .env file with generated secrets")
    print("⚠️  IMPORTANT: Keep your .env file secure and never commit it!")

def create_directories():
    """Create necessary directories"""
    print_header("Creating Project Directories")

    directories = [
        'terraform/workspaces',
        'logs',
        'data',
        'backups',
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created {directory}/")

def install_dependencies():
    """Install Python dependencies"""
    print_header("Installing Python Dependencies")

    response = input("Install Python dependencies from requirements.txt? (Y/n): ")
    if response.lower() != 'n':
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                         check=True)
            print("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing dependencies: {e}")
            return False

    return True

def initialize_database():
    """Initialize the database"""
    print_header("Database Initialization")

    response = input("Initialize database tables? (y/N): ")
    if response.lower() == 'y':
        try:
            from database.session import init_db, create_test_user, SessionLocal

            print("Creating database tables...")
            init_db()
            print("✅ Database tables created")

            # Create default admin user
            response = input("Create default admin user? (y/N): ")
            if response.lower() == 'y':
                db = SessionLocal()
                try:
                    create_test_user(db, username="admin", password="admin123")
                    print("✅ Admin user created (username: admin, password: admin123)")
                    print("⚠️  IMPORTANT: Change the default password in production!")
                finally:
                    db.close()

        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            print("   You can run this later with: python -c 'from database.session import init_db; init_db()'")

def print_next_steps():
    """Print next steps for the user"""
    print_header("Setup Complete! 🎉")

    print("""
Next steps:

1. Configure your database:
   - Start PostgreSQL: sudo systemctl start postgresql
   - Create database: createdb infraagent
   - Update DATABASE_URL in .env if needed

2. Configure AWS credentials:
   - Add credentials via the web interface, or
   - Set per-user credentials through the API

3. Start the application:
   - Backend API:  python app.py
   - Frontend UI:  streamlit run frontend/streamlit_app.py

4. Access the application:
   - Frontend: http://localhost:8501
   - API Docs: http://localhost:8000/docs
   - Default login: admin / admin123

5. Test the agent:
   - "Create a VM in AWS"
   - "Show me my resources"
   - "What's my infrastructure costing?"

For more information, see README.md

Happy provisioning! 🏗️
""")

def main():
    """Main setup routine"""
    print_header("Infrastructure Provisioning Agent - Setup")

    # Check prerequisites
    print_header("Checking Prerequisites")
    check_python_version()
    check_terraform()
    check_postgresql()

    # Setup steps
    create_directories()
    create_env_file()

    # Install dependencies
    if not install_dependencies():
        print("\n⚠️  Continuing without installing dependencies...")

    # Initialize database
    initialize_database()

    # Print next steps
    print_next_steps()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
