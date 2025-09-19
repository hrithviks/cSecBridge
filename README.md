# CSecBridge 🌉
A hybrid security gateway for managing multi-cloud IAM.

CSecBridge is a Flask-based application designed to bridge the gap between traditional, on-premise access management solutions and modern multi-cloud environments (AWS, Azure, GCP). It provides a centralized API to process access requests and a continuous reconciliation process to prevent configuration drift.

The core philosophy is to maintain a local "source of truth" for permissions and use a sweeper process to ensure the state in the cloud always matches this intended configuration.

# Key Features ✨
- Centralized API: A simple REST API to accept access requests from legacy systems.
- Drift Detection & Remediation: A background "sweeper" process that audits cloud permissions against the local database and automatically corrects any discrepancies.

```graph TD
    A[Legacy System] -->|Access Request (API Call)| B(CSecBridge API - Flask)
    B --> C{Database - PostgreSQL}
    C -->|Desired State| D[Sweeper Process]
    D --> E{Cloud Provider 1 - AWS}
    D --> F{Cloud Provider 2 - Azure}
    D --> G{Cloud Provider 3 - GCP}
    E -->|Audit & Remediate| H[Cloud IAM]
    F -->|Audit & Remediate| H
    G -->|Audit & Remediate| H
    H -->|Actual State| D
```

1.  **API Server (Flask)**: Receives access requests, validates them, and updates the local database with the desired state.
2.  **Database (PostgreSQL)**: Acts as the single source of truth for all IAM permissions across all integrated cloud providers.
3.  **Sweeper Process**: Periodically reads the desired state from the database, queries the actual state from each cloud provider, identifies discrepancies (drift), and applies necessary changes to align the cloud state with the desired state.
4.  **Cloud Connectors**: Modular components within the sweeper process that abstract away cloud-specific API calls for AWS, Azure, and GCP.

# Getting Started 🚀

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

## Prerequisites

*   Python 3.8+
*   pip (for dependency management)
*   Docker (For running PostgreSQL and deployment)
*   AWS, Azure, GCP accounts with appropriate IAM permissions for CSecBridge to manage.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/csecbridge.git
    cd csecbridge
    ```

2.  **Install dependencies using pip:**
    ```bash
    pip install -r requirements.txt

- Modular Cloud Connectors: Easily extensible design to add support for different cloud providers or services.
- State Management: Uses a local database to maintain the desired state of all permissions.
- Lightweight & Deployable: Built with Python and Flask, making it easy to containerize and deploy anywhere.    poetry shell
    ```

3.  **Set up environment variables:**
    Ensure that the necessary environment variables (e.g., `DATABASE_URL`, cloud provider credentials) are set in your environment. Refer to `.env.example` for a list of required variables.

4.  **Run database migrations:**
    ```bash
    flask db upgrade
    ```

5.  **Start the Flask API server:**
    ```bash
    flask run
    ```

6.  **Start the Sweeper process (in a separate terminal):**
    ```bash
    python -m csecbridge.sweeper.run
    ```

## Project Structure 📂

```
csecbridge/
├── api/                     # Flask API server
│   ├── __init__.py
│   ├── routes.py            # Defines API endpoints
│   └── models.py            # API-specific data models (e.g., request/response schemas)
├── database/                # Database models and migrations
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy models for desired state
│   └── migrations/
├── sweeper/                 # Background reconciliation process
│   ├── __init__.py
│   ├── run.py               # Entry point for the sweeper
│   ├── cloud_connectors/    # Cloud-specific IAM interaction logic
│   │   ├── __init__.py
│   │   ├── aws.py
│   │   ├── azure.py
│   │   └── gcp.py
│   └── core.py              # Sweeper core logic (drift detection, remediation)
├── config.py                # Application configuration
├── requirements.txt         # Python dependencies
├── .env.example             # Example environment variables
└── README.md
```

# License 📄
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
