# Quick Start Guide

## ✅ Installation Successful!

Your dependencies have been installed successfully on Python 3.13.

## Next Steps

### 1. Generate Environment Configuration

Run the setup script to create your `.env` file with secure keys:

```bash
python3 setup.py
```

This will:
- Create `.env` with secure encryption keys
- Create necessary directories
- Optionally initialize the database
- Create default admin user

### 2. Manual Setup (Alternative)

If you prefer manual setup:

```bash
# Create .env file
cp .env.example .env

# Generate secure keys
python3 -c "from cryptography.fernet import Fernet; print('SECRET_KEY=' + Fernet.generate_key().decode()); print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# Update .env with the generated keys
```

### 3. Initialize Database

**Option A: Using Make**
```bash
make init-db
make create-admin
```

**Option B: Manual**
```bash
# Initialize database
python3 -c "from database.session import init_db; init_db()"

# Create admin user
python3 -c "
from database.session import SessionLocal, create_test_user
db = SessionLocal()
create_test_user(db, 'admin', 'admin123')
db.close()
print('Admin user created: admin / admin123')
"
```

### 4. Start the Application

**Option A: Both services (recommended)**
```bash
make dev
```

**Option B: Separately**

Terminal 1 (API):
```bash
python3 app.py
```

Terminal 2 (Frontend):
```bash
streamlit run frontend/streamlit_app.py
```

### 5. Access the Application

- **Frontend**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

**Default Login**:
- Username: `admin`
- Password: `admin123`

## Testing the System

### Basic Test

1. Open http://localhost:8501
2. Login with `admin` / `admin123`
3. Configure AWS credentials in the sidebar (optional for testing)
4. Try these commands:
   - "Create a VM in AWS"
   - "Show me my resources"
   - "What's my infrastructure costing?"

### API Test

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Get token from response, then test chat
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a VM in AWS", "session_id": "test-123"}'
```

## Troubleshooting

### Database Connection Error

```bash
# Check if PostgreSQL is running
# Mac:
brew services start postgresql

# Linux:
sudo systemctl start postgresql

# Create database
createdb infraagent
```

### Module Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill it if needed
kill -9 <PID>

# Or use different ports
API_PORT=8001 python3 app.py
```

### Terraform Not Found

```bash
# Mac:
brew install terraform

# Linux:
sudo apt-get install terraform

# Or download from:
# https://www.terraform.io/downloads
```

## Project Structure

```
infrastructure-agent/
├── agent/              # AI agent logic
│   ├── main.py
│   ├── intent_parser.py
│   ├── response_generator.py
│   └── cost_estimator.py
├── mcp/                # MCP protocol
│   ├── client.py
│   └── server/
├── security/           # Auth & encryption
│   ├── auth.py
│   ├── credentials.py
│   └── rbac.py
├── database/           # Database models
│   ├── models.py
│   └── session.py
├── frontend/           # UI
│   └── streamlit_app.py
├── app.py              # Main API
└── requirements.txt    # Dependencies
```

## Available Commands (Make)

```bash
make help           # Show all commands
make install        # Install dependencies
make dev            # Run both API and frontend
make api            # Run API only
make frontend       # Run frontend only
make init-db        # Initialize database
make create-admin   # Create admin user
make test           # Run tests
make clean          # Clean temporary files
```

## Common Tasks

### Add New User

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "password123",
    "email": "user@example.com",
    "full_name": "New User"
  }'
```

### Store AWS Credentials

Via Frontend:
1. Login
2. Click "Configure AWS" in sidebar
3. Enter credentials
4. Click "Save Credentials"

Via API:
```bash
curl -X POST http://localhost:8000/credentials/store \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "credentials": {
      "aws_access_key": "AKIA...",
      "aws_secret_key": "..."
    },
    "region": "us-east-1"
  }'
```

### List Resources

```bash
curl -X GET http://localhost:8000/resources \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Security Notes

⚠️ **IMPORTANT for Production:**

1. **Change default passwords** immediately
2. **Generate new SECRET_KEY and ENCRYPTION_KEY**
3. **Use HTTPS** in production
4. **Configure CORS** for specific origins
5. **Set up proper logging and monitoring**
6. **Use environment-specific configs**
7. **Never commit `.env` to version control**

## Need Help?

- Check [README.md](README.md) for full documentation
- Check [IMPLEMENTATION.md](IMPLEMENTATION.md) for technical details
- Review API docs at http://localhost:8000/docs
- Check logs in `logs/infraagent.log`

## Success! 🎉

Your Infrastructure Provisioning Agent is ready to use. Start by running:

```bash
make dev
```

Then open http://localhost:8501 and start provisioning infrastructure with natural language!
