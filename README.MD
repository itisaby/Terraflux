# 🏗️ Infrastructure Provisioning Agent

A conversational AI agent that provisions and manages cloud infrastructure through natural language interactions, powered by **Agentic AI**, **MCP (Model Context Protocol)**, and **Terraform**.

## ✨ Features

- **🗣️ Natural Language Interface**: "Create a VM in AWS" → Provisions EC2 instance
- **🔒 Secure Credential Management**: AWS credentials never exposed to LLMs
- **🏗️ Terraform Backend**: Professional infrastructure-as-code approach
- **🔄 MCP Integration**: Secure tool communication protocol
- **💰 Cost Estimation**: Shows estimated costs before provisioning
- **👤 Multi-User Support**: User authentication and RBAC
- **📊 Real-time Chat UI**: Modern web interface with Streamlit
- **🔍 Audit Logging**: Complete audit trail of all operations
- **🌐 Multi-Cloud Ready**: Extensible for AWS, Azure, GCP

## 🏛️ Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[Web Chat Interface]
        API[REST API Gateway]
    end

    subgraph "Agent Layer"
        AGENT[AI Agent Engine]
        NLP[Intent Parser]
        RESP[Response Generator]
    end

    subgraph "MCP Layer"
        CLIENT[MCP Client]
        SERVER[Terraform MCP Server]
    end

    subgraph "Security Layer"
        AUTH[User Authentication]
        CREDS[Encrypted Credential Store]
        RBAC[Role-Based Access Control]
    end

    subgraph "Terraform Engine"
        TEMPLATES[Template Generator]
        CLI[Terraform CLI]
        STATE[State Management]
    end

    subgraph "Cloud Providers"
        AWS[AWS APIs]
        AZURE[Azure APIs]
        GCP[GCP APIs]
    end

    subgraph "Storage"
        DB[(User Profiles DB)]
        TFSTATE[(Terraform State)]
        LOGS[(Audit Logs)]
    end

    UI --> API
    API --> AGENT
    AGENT --> NLP
    AGENT --> RESP
    AGENT --> CLIENT
    CLIENT --> SERVER

    SERVER --> AUTH
    AUTH --> CREDS
    AUTH --> RBAC

    SERVER --> TEMPLATES
    TEMPLATES --> CLI
    CLI --> STATE

    CLI --> AWS
    CLI --> AZURE
    CLI --> GCP

    AUTH --> DB
    STATE --> TFSTATE
    SERVER --> LOGS

    style AGENT fill:#e1f5fe
    style SERVER fill:#f3e5f5
    style CREDS fill:#ffebee
    style CLI fill:#e8f5e8
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Terraform 1.0+
- Docker (optional)

### 1. Clone and Setup

```bash
git clone <your-repo>
cd infrastructure-agent

# Run the setup script
python setup.py

# Or use make
make setup
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/infraagent

# Security (generate proper keys for production!)
SECRET_KEY=your-jwt-secret-key-here
ENCRYPTION_KEY=your-fernet-encryption-key-here

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
# Or: make install
```

### 4. Initialize Database

```bash
# Start PostgreSQL (if not running)
# Then create tables
make init-db
```

### 5. Run the Application

```bash
# Start both API and frontend
make dev

# Or run separately:
python app.py &                    # API server (port 8000)
streamlit run frontend/app.py      # Frontend (port 8501)
```

### 6. Access the Application

- **Frontend**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Default Login**: username=`admin`, password=`admin123`

## 💬 Usage Examples

### Basic Infrastructure Commands

```
User: "Create a VM in AWS"
Agent: "I'll create a t3.micro EC2 instance in us-east-1.
        Estimated cost: $10.50/month. Shall I proceed?"

User: "Yes, apply it"
Agent: "✅ EC2 instance created successfully!
        Instance ID: i-1234567890abcdef0
        Public IP: 54.123.45.67"
```

```
User: "Set up a database with web server"
Agent: "I'll provision:
        • EC2 instance (t3.micro) for web server
        • RDS MySQL database (db.t3.micro)
        • Security groups for proper access

        Estimated monthly cost: $35.80
        Should I create this infrastructure?"
```

```
User: "What infrastructure do I have running?"
Agent: "Current resources:
        • 2 EC2 instances (us-east-1)
        • 1 RDS database (MySQL 8.0)
        • 1 S3 bucket
        • 1 Application Load Balancer

        Total estimated cost: $127.50/month"
```

### Advanced Commands

```
User: "Scale my web servers to 3 instances in Oregon"
User: "Create a development environment"
User: "Set up CI/CD infrastructure with S3 and CodeBuild"
User: "Show me cost breakdown by service"
User: "Destroy all resources in staging environment"
```

## 🔧 Configuration

### User Management

1. **Web Interface**: Configure AWS credentials in the sidebar
2. **API**: Use `/auth/login` endpoint for authentication
3. **Database**: Users stored in PostgreSQL with encrypted credentials

### AWS Credentials Setup

The system securely stores AWS credentials per user:

```python
# Credentials are encrypted and never exposed to LLMs
await credential_manager.store_user_credentials(
    user_id="user123",
    provider="aws",
    credentials={
        "aws_access_key": "AKIA...",
        "aws_secret_key": "xyz...",
        "region": "us-east-1"
    }
)
```

### Adding New Resources

1. **Create Terraform Template**: Add to `mcp/server/templates/aws/`
2. **Update Intent Parser**: Add resource patterns to `agent/intent_parser.py`
3. **Add MCP Tool**: Extend `mcp/server/terraform_server.py`

Example template (`new_resource.tf.j2`):

```hcl
resource "aws_new_service" "{{ resource_name }}" {
  name = "{{ resource_name }}-{{ environment }}"
  type = "{{ config.type | default('standard') }}"

  tags = {
    Name        = "{{ resource_name }}-{{ environment }}"
    Environment = "{{ environment }}"
    ManagedBy   = "InfraAgent"
  }
}

output "{{ resource_name }}_id" {
  value = aws_new_service.{{ resource_name }}.id
}
```

## 🧪 Testing

### Run Tests

```bash
# Run all tests
make test

# Test specific components
python -m pytest tests/test_agent.py -v
python -m pytest tests/test_mcp.py -v
python -m pytest tests/test_terraform.py -v
```

### Manual Testing

```bash
# Test agent functionality
python -c "
from agent.main import InfraAgent
from agent.intent_parser import IntentParser

parser = IntentParser()
intent = parser.parse('Create a VM in AWS')
print(intent)
"

# Test MCP client
python mcp/client.py
```

## 🐳 Docker Deployment

### Development

```bash
docker-compose up -d
```

### Production

```bash
# Build image
docker build -t infrastructure-agent .

# Run with proper environment
docker run -e DATABASE_URL="postgresql://..." \
           -e SECRET_KEY="..." \
           -p 8000:8000 \
           infrastructure-agent
```

## 🔒 Security

### Credential Security

- ✅ AWS credentials encrypted with Fernet
- ✅ Never passed to LLM models
- ✅ Isolated in MCP server process
- ✅ User-specific credential storage

### Authentication

- ✅ JWT-based authentication
- ✅ Role-based access control (RBAC)
- ✅ Session management
- ✅ Password hashing with PBKDF2

### Infrastructure Security

- ✅ Terraform state encryption
- ✅ Audit logging for all operations
- ✅ Resource tagging for ownership
- ✅ Network security groups by default

## 📊 Monitoring & Logging

### Application Logs

```bash
# View real-time logs
tail -f logs/infraagent.log

# View specific user actions
grep "user-123" logs/infraagent.log
```

### Database Monitoring

```sql
-- Check recent infrastructure requests
SELECT * FROM infrastructure_requests
ORDER BY created_at DESC LIMIT 10;

-- View audit logs
SELECT action, resource_type, timestamp
FROM audit_logs
WHERE user_id = 'user-123'
ORDER BY timestamp DESC;
```

### Cost Monitoring

The system provides cost estimates before provisioning:

- Real-time cost calculation
- Monthly cost projections
- Resource cost breakdown
- Budget alerts (planned feature)

## 🚧 Development

### Project Structure

```
infrastructure-agent/
├── agent/                 # AI agent core logic
│   ├── main.py           # Agent orchestrator
│   ├── intent_parser.py  # NLP intent parsing
│   └── response_generator.py
├── mcp/                  # MCP client/server
│   ├── client.py         # MCP client
│   └── server/           # Terraform MCP server
├── security/             # Auth & credentials
│   ├── auth.py          # Authentication
│   ├── credentials.py   # Encrypted storage
│   └── rbac.py          # Access control
├── frontend/            # Streamlit UI
├── terraform/           # TF workspaces & modules
└── database/           # SQLAlchemy models
```

### Adding New Features

1. **New Cloud Provider**:

   - Add templates in `mcp/server/templates/azure/`
   - Extend `intent_parser.py` patterns
   - Add provider-specific tools

2. **New Resource Types**:

   - Create Terraform template
   - Update intent parsing
   - Add cost estimation logic

3. **Enhanced AI**:
   - Improve natural language processing
   - Add conversation context
   - Implement learning from user preferences

### API Endpoints

| Endpoint          | Method | Description                    |
| ----------------- | ------ | ------------------------------ |
| `/chat`           | POST   | Main chat interface            |
| `/confirm-action` | POST   | Confirm infrastructure changes |
| `/auth/login`     | POST   | User authentication            |
| `/resources`      | GET    | List user resources            |
| `/costs`          | GET    | Get cost estimates             |
| `/audit`          | GET    | Audit log access               |

## 🤝 Contributing

### Development Setup

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Run tests: `make test`
4. Submit pull request

### Code Style

- Use Black for formatting: `black .`
- Follow PEP 8 conventions
- Add type hints for all functions
- Write comprehensive docstrings

## 🐛 Troubleshooting

### Common Issues

**1. Database Connection Error**

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify database URL in .env
echo $DATABASE_URL
```

**2. MCP Server Connection Failed**

```bash
# Check if MCP server is running
ps aux | grep terraform_server

# Verify port availability
netstat -ln | grep 8001
```

**3. Terraform Execution Failed**

```bash
# Check Terraform installation
terraform --version

# Verify AWS credentials
aws sts get-caller-identity
```

**4. Frontend Not Loading**

```bash
# Check if Streamlit is running
ps aux | grep streamlit

# Verify port 8501 is available
curl http://localhost:8501
```

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python app.py
```

### Reset Everything

```bash
# Reset database
make reset-db

# Clean workspaces
make clean

# Restart services
make dev
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Anthropic** for Claude AI and MCP protocol
- **HashiCorp** for Terraform
- **Streamlit** for the amazing web framework
- **FastAPI** for the robust API framework

---

**🎉 Happy Infrastructure Provisioning!**

Start with: `make setup && make dev` and visit http://localhost:8501
