"""
Personalized Onboarding Plan Generator service.

Generates role-, seniority-, and technology-tailored onboarding plans grounded in the
NovaByte knowledge base (setup guides, architecture, standards, and checklists).
Persists structured plans to the SQLite database for stateful session continuity.
"""
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
import uuid
import logging

from app.models.schemas import OnboardingTask, OnboardingPlan
from app.db import models

logger = logging.getLogger(__name__)


def _normalize_stack(stack: Optional[List[str]]) -> List[str]:
    if not stack:
        return []
    if isinstance(stack, str):
        return [s.strip().lower() for s in stack.split(",") if s.strip()]
    return [str(s).strip().lower() for s in stack if str(s).strip()]


def generate_onboarding_plan(
    role: str,
    experience_level: str,
    technology_stack: Optional[List[str]] = None,
    team: Optional[str] = None,
    session_id: Optional[str] = None,
) -> OnboardingPlan:
    """
    Generate a personalized, ordered onboarding plan tailored to the employee's
    role, experience level, tech stack, and squad/team.
    """
    clean_role = (role or "general").lower().strip()
    clean_role = clean_role.replace("-", "").replace(" ", "").replace("_", "")
    clean_level = (experience_level or "junior").lower().strip()
    stack = _normalize_stack(technology_stack)
    primary_tech = stack[0].title() if stack else ("Node.js" if clean_role == "frontend" else "Python")
    team_name = team or f"{clean_role.capitalize()} Engineering"
    session_key = session_id or str(uuid.uuid4())

    tasks: List[OnboardingTask] = []

    node_stack = any(k in s for s in stack for k in ("node", "javascript", "typescript", "express", "nestjs"))
    python_stack = any(k in s for s in stack for k in ("python", "django", "fastapi", "flask"))

    # =========================================================================
    # 0. Senior Backend (Squad Alpha for Python, Squad Beta for Node.js)
    # =========================================================================
    if clean_role == "backend" and clean_level in ("senior", "lead", "staff", "principal"):
        if python_stack and not node_stack:
            tech_name = "Python"
            squad, lead = "Backend Squad Alpha (Workflows)", "Sneha Kulkarni"
            repos, main_repo = "workflow-core and workflow-executor", "workflow-core"
            guide, tools = "Guide 2 (Python Backend Setup)", "Python 3.11 via pyenv and Poetry"
            topic, metrics = "workflow.executions", "workflow execution success rate, latency p95 and error rate"
            standup = "#standup-backend-alpha"
            first_task = (
                "Agree a design-level first ticket on workflow-core (retry logic, state management or versioning) "
                "with Squad Lead Sneha Kulkarni and Staff Engineer Rahul Verma, then deliver it with tests and a design note."
            )
        else:
            tech_name = "Node.js"
            squad, lead = "Backend Squad Beta (Connectors & Notifications)", "Arjun Mehta"
            repos, main_repo = "connector-runtime and notification-service", "connector-runtime"
            guide, tools = "Guide 1 (Node.js Backend Setup)", "Node.js 20 via nvm and pnpm"
            topic, metrics = "notifications.outbound", "connector execution success rate, notification delivery rate and latency"
            standup = "#standup-backend-beta"
            first_task = (
                "Pick up FLOW-SR-001 (circuit breaker for external connector calls, emitting state changes to the "
                "connector.circuit.events Kafka topic), with integration tests for simulated failures and an updated README."
            )
        tasks = [
            OnboardingTask(
                task_id="SBE-01",
                order=1,
                title="Environment Setup",
                description=f"Follow {guide}: install {tools}, plus Docker Desktop.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Terminal output showing the runtime and package manager versions.",
            ),
            OnboardingTask(
                task_id="SBE-02",
                order=2,
                title="Squad Repositories & Channels",
                description=f"Join {squad}, led by {lead}: clone {repos}, install dependencies, and join {standup}.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Both repositories cloned with dependencies installed.",
            ),
            OnboardingTask(
                task_id="SBE-03",
                order=3,
                title="Run Services Locally",
                description=f"Start PostgreSQL, Redis and Kafka with `docker-compose -f docker-compose.dev.yml up -d`, then run {main_repo} and its full test suite.",
                category="Service Execution",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required=f"{main_repo} running locally with a passing test suite.",
            ),
            OnboardingTask(
                task_id="SBE-04",
                order=4,
                title="System Architecture Deep Dive",
                description=f"Read KB-003 end to end: the domain breakdown, calls through the gateway, and the Kafka topic {topic}. Map how {main_repo} behaves when one of its dependencies is down.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required=f"Written failure-mode notes for {main_repo}.",
            ),
            OnboardingTask(
                task_id="SBE-05",
                order=5,
                title="Code Review & Reliability Standards",
                description=f"Review KB-002 code review rules (2 approvals, at least one code owner, respond within 4 business hours); as a senior you will review others' PRs. Follow the squad's metrics ({metrics}) in Datadog and book on-call shadow shifts (FAQ Q23).",
                category="Standards Review",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="First PR review completed and on-call shadow shifts booked.",
            ),
            OnboardingTask(
                task_id="SBE-06",
                order=6,
                title="Senior Starter Ticket",
                description=first_task,
                category="First Task",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="GitHub PR link with tests.",
            ),
        ]

    # =========================================================================
    # 1. Backend Intern, or any backend engineer on a Node.js / JavaScript stack
    # =========================================================================
    elif clean_role == "backend" and not python_stack and (clean_level == "intern" or node_stack):
        # These tasks are Node.js-specific (nvm, pnpm, connector-runtime), so name Node.js explicitly.
        tech_name = "Node.js"
        tasks = [
            OnboardingTask(
                task_id="BI-01",
                order=1,
                title="Environment Setup",
                description=f"Install {tech_name} 20 via nvm, pnpm, Docker Desktop, and VS Code with ESLint and Prettier extensions (ref: setup_guides.md).",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required=f"Terminal output of `{tech_name.lower()} -v` and `docker --version`.",
            ),
            OnboardingTask(
                task_id="BI-02",
                order=2,
                title="Repository Access",
                description="Accept GitHub organization invite and clone the assigned connector-runtime repository.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Confirmation of repository cloned locally with `.env` configured.",
            ),
            OnboardingTask(
                task_id="BI-03",
                order=3,
                title="Run Local Server",
                description="Start dependencies using Docker Compose, execute database migrations, seed demo data, and start the local server.",
                category="Service Execution",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Terminal log showing server listening and passing health check on port 3000.",
            ),
            OnboardingTask(
                task_id="BI-04",
                order=4,
                title="Backend Architecture Review",
                description="Read Architecture Documentation (KB-003) Backend section covering connector runtime, plugin lifecycle, and message queues.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Summary of the connector runtime lifecycle and plugin isolation model.",
            ),
            OnboardingTask(
                task_id="BI-05",
                order=5,
                title="API Standards Review",
                description="Review Engineering Standards (KB-002) covering REST conventions, HTTP status codes, error payload schemas, and Git PR rules.",
                category="API Standards",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Acknowledgment of PR title conventions and REST error handling standards.",
            ),
            OnboardingTask(
                task_id="BI-06",
                order=6,
                title="Starter Task",
                description="Pick up starter ticket FLOW-INTERN-001 (Fix validation bug on connector payload), add unit tests, and submit PR.",
                category="First Task",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Link to submitted pull request with unit test coverage.",
            ),
        ]

    # =========================================================================
    # 2. Frontend Senior + React
    # =========================================================================
    elif clean_role == "frontend" and clean_level in ("senior", "lead", "staff"):
        tech_name = "React"
        tasks = [
            OnboardingTask(
                task_id="SFR-01",
                order=1,
                title="Environment & Design System Setup",
                description="Setup Node 20, clone flowengine-web, start development server, and explore Storybook design system (@novabyte/ui-kit).",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Storybook and web client running locally with zero build errors.",
            ),
            OnboardingTask(
                task_id="SFR-02",
                order=2,
                title="Frontend Architecture & State Review",
                description="Deep dive into KB-003 Frontend Architecture, analyzing Zustand store modularization, React Query caching strategies, and router layout.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Architecture review notes comparing global vs server state patterns.",
            ),
            OnboardingTask(
                task_id="SFR-03",
                order=3,
                title="Performance Standards & Web Vitals Audit",
                description="Review KB-002 Frontend Standards, TypeScript strict mode rules, Core Web Vitals thresholds (LCP < 2.5s, CLS < 0.1), and accessibility (a11y).",
                category="API Standards",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Verification of local bundle analysis and accessibility linting pass.",
            ),
            OnboardingTask(
                task_id="SFR-04",
                order=4,
                title="Cross-Team Stakeholder Alignment",
                description="Conduct 1:1 intro syncs with Product Manager, QA Lead, and Backend Squad Leads to align on upcoming epic deliverables.",
                category="Stakeholder Alignment",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Summary of key dependencies and frontend epic priorities discussed.",
            ),
            OnboardingTask(
                task_id="SFR-05",
                order=5,
                title="Sprint Planning & Technical Debt Review",
                description="Review current Jira sprint board, component library backlog, and propose frontend performance or refactoring optimizations.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="List of prioritized frontend improvements reviewed with squad lead.",
            ),
            OnboardingTask(
                task_id="SFR-06",
                order=6,
                title="Lead Feature PR & Architecture Delivery",
                description="Pick up complex UI module ticket (FLOW-FE-SENIOR-001: Dynamic Flow Builder Canvas), write RTL integration tests, and lead team PR review.",
                category="First Task",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Link to merged high-impact pull request with comprehensive test suite.",
            ),
        ]

    # =========================================================================
    # 3. DevOps Junior
    # =========================================================================
    elif clean_role in ("devops", "platform", "sre", "infrastructure") and clean_level in ("junior", "intern"):
        tech_name = "Docker/Kubernetes/AWS"
        tasks = [
            OnboardingTask(
                task_id="JDO-01",
                order=1,
                title="Cloud Access & VPN Configuration",
                description="Request AWS IAM developer credentials, configure AWS CLI with novabyte profile, and setup WireGuard VPN.",
                category="Cloud Infrastructure",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Terminal output of `aws sts get-caller-identity` and VPN handshake.",
            ),
            OnboardingTask(
                task_id="JDO-02",
                order=2,
                title="Toolchain & Kubernetes Cluster Setup",
                description="Install Terraform, kubectl, Helm, and ArgoCD CLI; connect to dev/staging EKS clusters via kubectl.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Terminal output of `kubectl cluster-info` and `terraform version`.",
            ),
            OnboardingTask(
                task_id="JDO-03",
                order=3,
                title="Infrastructure Repository Setup",
                description="Clone the centralized terraform-infrastructure repository and configure git pre-commit hooks for terraform fmt and tflint.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Pre-commit checks passing on infrastructure repository.",
            ),
            OnboardingTask(
                task_id="JDO-04",
                order=4,
                title="Cloud Architecture & Network Topology Review",
                description="Read KB-003 Infrastructure section detailing VPC subnets, EKS node groups, ingress controllers, and security group isolation.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Summary diagram or notes on dev vs staging VPC isolation.",
            ),
            OnboardingTask(
                task_id="JDO-05",
                order=5,
                title="CI/CD & Observability Standards Review",
                description="Review KB-002 Deployment Standards, GitHub Actions reusable workflows, ArgoCD GitOps sync strategies, and Datadog alert SLOs.",
                category="API Standards",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Walkthrough completion of automated staging deployment pipeline.",
            ),
            OnboardingTask(
                task_id="JDO-06",
                order=6,
                title="Infrastructure Starter Ticket",
                description="Pick up starter ticket FLOW-OPS-001 (Automate pod resource limits and HPA configuration on dev EKS), test plan, and submit PR.",
                category="First Task",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="GitHub PR link with `terraform plan` output attached.",
            ),
        ]

    # =========================================================================
    # 4. Junior Backend (Python / General)
    # =========================================================================
    elif clean_role == "backend" and clean_level in ("intern", "junior", "mid"):
        tech_name = "Python" if any("python" in s or "django" in s or "fastapi" in s for s in stack) else primary_tech
        tasks = [
            OnboardingTask(
                task_id="JBP-01",
                order=1,
                title="Python & Toolchain Setup",
                description="Install Python 3.11 via pyenv, Poetry package manager, Docker Desktop, and VS Code with Pylance.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Terminal output of `poetry --version` and active python virtual environment.",
            ),
            OnboardingTask(
                task_id="JBP-02",
                order=2,
                title="Repository Access & Local Config",
                description="Clone assigned workflow-core repository, run `poetry install`, and configure local `.env`.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Successful dependency installation and git status clean.",
            ),
            OnboardingTask(
                task_id="JBP-03",
                order=3,
                title="Run Local Server & Database Migrations",
                description="Launch PostgreSQL/Redis with Docker Compose, apply Alembic migrations, and verify Swagger docs load at localhost:8000/docs.",
                category="Service Execution",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Server log showing Uvicorn running and Swagger UI response 200.",
            ),
            OnboardingTask(
                task_id="JBP-04",
                order=4,
                title="Backend & Data Architecture Review",
                description="Review KB-003 Backend & Data Architecture covering asynchronous task queues, SQLAlchemy ORM models, and Redis caching.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Summary of data model lifecycle and transactional boundaries.",
            ),
            OnboardingTask(
                task_id="JBP-05",
                order=5,
                title="API & Testing Standards Review",
                description="Review KB-002 REST standards, pytest fixture conventions, and verify minimum 80% test coverage requirement.",
                category="API Standards",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="Output of `pytest --cov` executing locally.",
            ),
            OnboardingTask(
                task_id="JBP-06",
                order=6,
                title="Starter Task",
                description="Pick up starter ticket FLOW-JR-001 (Add schema validation to workflow endpoint), write unit tests, and open PR.",
                category="First Task",
                required=True,
                status="Pending",
                role="backend",
                technology=tech_name,
                evidence_required="GitHub PR link with test coverage report.",
            ),
        ]

    # =========================================================================
    # 5. Junior Frontend (React / TypeScript)
    # =========================================================================
    elif clean_role == "frontend":
        tech_name = "React"
        tasks = [
            OnboardingTask(
                task_id="JFR-01",
                order=1,
                title="Frontend Environment Setup",
                description="Install Node 20, pnpm, and VS Code extensions for Tailwind CSS and ESLint.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Terminal output of `node -v` and `pnpm -v`.",
            ),
            OnboardingTask(
                task_id="JFR-02",
                order=2,
                title="Repository Access",
                description="Clone flowengine-web repository and run `pnpm install`.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Local repository cloned and `.env.local` configured.",
            ),
            OnboardingTask(
                task_id="JFR-03",
                order=3,
                title="Run Development Server & Storybook",
                description="Start local dev server (`pnpm dev`) and Storybook (`pnpm storybook`) to explore @novabyte/ui-kit components.",
                category="Service Execution",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Browser screenshot or terminal output showing Vite running on port 5173.",
            ),
            OnboardingTask(
                task_id="JFR-04",
                order=4,
                title="Frontend Architecture Review",
                description="Read KB-003 Frontend section covering React Router, Zustand stores, and React Query data fetching.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Notes on component hierarchy and store design.",
            ),
            OnboardingTask(
                task_id="JFR-05",
                order=5,
                title="Code Style & UI Standards Review",
                description="Review KB-002 TypeScript style guide, Tailwind naming standards, and PR screenshot submission rules.",
                category="API Standards",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="Verification of clean `pnpm lint` execution.",
            ),
            OnboardingTask(
                task_id="JFR-06",
                order=6,
                title="Starter Task",
                description="Pick up starter ticket FLOW-FE-001 (Enhance data table pagination component), add React Testing Library tests, and submit PR.",
                category="First Task",
                required=True,
                status="Pending",
                role="frontend",
                technology=tech_name,
                evidence_required="GitHub PR link with component tests and screenshots.",
            ),
        ]

    # =========================================================================
    # 6. DevOps / Platform (mid, senior, lead)
    # =========================================================================
    elif clean_role in ("devops", "platform", "sre", "infrastructure"):
        tech_name = "Terraform/Kubernetes/AWS"
        tasks = [
            OnboardingTask(
                task_id="SDO-01",
                order=1,
                title="Cloud Access, VPN & Least-Privilege Review",
                description="Request AWS IAM credentials from Platform Lead Rohan Saxena, configure the AWS CLI novabyte profile and WireGuard VPN, and confirm your access follows the Principle of Least Privilege (policies.md).",
                category="Cloud Infrastructure",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Terminal output of `aws sts get-caller-identity` and a successful VPN handshake.",
            ),
            OnboardingTask(
                task_id="SDO-02",
                order=2,
                title="Infrastructure Toolchain & Cluster Access",
                description="Follow Guide 4 (DevOps / Infrastructure Setup): install Terraform, kubectl, Helm and the ArgoCD CLI, then connect to the dev and staging EKS clusters.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Terminal output of `kubectl cluster-info` and `terraform version`.",
            ),
            OnboardingTask(
                task_id="SDO-03",
                order=3,
                title="Infrastructure Repository & Helm Charts",
                description="Clone novabyte/infrastructure, review the Helm chart layout (helm-charts/*/values-dev|staging|prod.yaml), and run `terraform plan` against dev.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="`terraform plan` output for dev showing no unexpected changes.",
            ),
            OnboardingTask(
                task_id="SDO-04",
                order=4,
                title="Production Architecture & Reliability Review",
                description="Read KB-003 Infrastructure: EKS namespaces and replicas, the analytics CronJobs, the Datadog DaemonSet, and the GitHub Actions to ArgoCD deployment flow. Note any single points of failure.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Short written summary of the deployment flow and reliability risks found.",
            ),
            OnboardingTask(
                task_id="SDO-05",
                order=5,
                title="Observability & Incident Response Readiness",
                description="Review the Datadog dashboards and the PagerDuty escalation path (on-call, then Squad Lead, then VP Engineering; acknowledge P1 incidents within 15 minutes), read docs/runbooks/, and schedule on-call shadow shifts (FAQ Q23).",
                category="Operations Readiness",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="Runbooks reviewed and on-call shadow shifts booked.",
            ),
            OnboardingTask(
                task_id="SDO-06",
                order=6,
                title="Infrastructure Starter Ticket",
                description="Pick up starter ticket FLOW-INFRA-001 (add Pod Disruption Budgets to all production services via Helm), test with a simulated node drain on dev, and get the plan reviewed by the Platform Lead.",
                category="First Task",
                required=True,
                status="Pending",
                role="devops",
                technology=tech_name,
                evidence_required="GitHub PR link with Helm diff and node-drain test results.",
            ),
        ]

    # =========================================================================
    # 7. ML / Data Engineering
    # =========================================================================
    elif clean_role in ("ml", "machinelearning", "data", "datascience", "mlengineer", "dataengineer"):
        tech_name = "Python/Spark"
        tasks = [
            OnboardingTask(
                task_id="MLE-01",
                order=1,
                title="Python & Data Toolchain Setup",
                description="Follow Guide 2 (Python Backend Setup, which covers Analytics): install Python 3.11 via pyenv, Poetry, and Docker Desktop.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="Terminal output of `python --version` and `poetry --version`.",
            ),
            OnboardingTask(
                task_id="MLE-02",
                order=2,
                title="Analytics Repositories & Data Access",
                description="Clone analytics-service and analytics-pipeline, run `poetry install`, and request read access to the novabyte_analytics PostgreSQL database from Data Lead Amit Sharma.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="Both repositories install cleanly and a read-only query on novabyte_analytics succeeds.",
            ),
            OnboardingTask(
                task_id="MLE-03",
                order=3,
                title="Run the Analytics Stack Locally",
                description="Start PostgreSQL, Redis and Kafka with `docker-compose -f docker-compose.dev.yml up -d`, run the analytics-service test suite, and complete one local analytics-pipeline run.",
                category="Service Execution",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="Passing test output and logs from a local pipeline run.",
            ),
            OnboardingTask(
                task_id="MLE-04",
                order=4,
                title="Data Architecture Review",
                description="Read KB-003: analytics-service (2 replicas) and the analytics-pipeline CronJob in the analytics namespace, the novabyte_analytics database, and how workflow events reach analytics.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="Notes or a diagram of the data flow from workflow events to analytics.",
            ),
            OnboardingTask(
                task_id="MLE-05",
                order=5,
                title="Data Handling & Quality Standards",
                description="Review the Data Handling & Privacy Policy and data classification levels (policies.md) and the Python coding standards (KB-002). Learn the Data Team's key metrics: pipeline freshness, data quality scores and model accuracy.",
                category="Standards Review",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="Confirmation of the data classification level for each dataset you will use.",
            ),
            OnboardingTask(
                task_id="MLE-06",
                order=6,
                title="First Data Team Task",
                description="Agree your first scoped ticket on analytics-pipeline or the ML-driven workflow recommendations with Data Lead Amit Sharma, implement it with tests, and open a PR.",
                category="First Task",
                required=True,
                status="Pending",
                role="ml",
                technology=tech_name,
                evidence_required="GitHub PR link with tests and a note on the data quality checks run.",
            ),
        ]

    # =========================================================================
    # 8. Fullstack (Node.js + React)
    # =========================================================================
    elif clean_role in ("fullstack",):
        tech_name = "Node.js + React"
        tasks = [
            OnboardingTask(
                task_id="FS-01",
                order=1,
                title="Full-Stack Environment Setup",
                description="Follow Guide 1 (Node.js Backend) and Guide 3 (React Frontend): install Node.js 20 via nvm, pnpm, and Docker Desktop.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="Terminal output of `node -v` and `pnpm -v`.",
            ),
            OnboardingTask(
                task_id="FS-02",
                order=2,
                title="Repository Access",
                description="Clone connector-runtime and flowengine-web, run `pnpm install` in each, and copy `.env.example` to `.env`.",
                category="Repository Access",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="Both repositories install without errors.",
            ),
            OnboardingTask(
                task_id="FS-03",
                order=3,
                title="Run the Full Stack Locally",
                description="Start PostgreSQL, Redis and Kafka with `docker-compose -f docker-compose.dev.yml up -d`, run connector-runtime, then `cd flowengine-web && pnpm dev` (port 3000).",
                category="Service Execution",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="Screenshot of flowengine-web on localhost:3000 talking to the local backend.",
            ),
            OnboardingTask(
                task_id="FS-04",
                order=4,
                title="Backend & Frontend Architecture Review",
                description="Read KB-003 for the Gateway to Connector Runtime request path and the flowengine-web frontend (React, TypeScript, Tailwind CSS, @novabyte/ui-kit). Browse the components in Storybook.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="Notes tracing one request from the UI through the gateway to a connector.",
            ),
            OnboardingTask(
                task_id="FS-05",
                order=5,
                title="API & Frontend Standards Review",
                description="Review KB-002 API standards (error response format, validation) and the frontend conventions. Keep PRs under 400 lines changed (FAQ).",
                category="API Standards",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="Checklist of the standards that apply to the starter tickets.",
            ),
            OnboardingTask(
                task_id="FS-06",
                order=6,
                title="Full-Stack Starter Tickets",
                description="Pick up FLOW-FS-001 (sanitize connector name and description in connector-runtime), then FLOW-FS-002 (status badge component in flowengine-web).",
                category="First Task",
                required=True,
                status="Pending",
                role="fullstack",
                technology=tech_name,
                evidence_required="GitHub PR links for both tickets with tests.",
            ),
        ]

    # =========================================================================
    # 9. Fallback / General Engineering
    # =========================================================================
    else:
        tech_name = primary_tech or "Full-Stack"
        tasks = [
            OnboardingTask(
                task_id="DEV-01",
                order=1,
                title="Development Environment Setup",
                description=f"Install toolchain for {tech_name}, Docker Desktop, and code editors as specified in KB-004.",
                category="Environment Setup",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="Terminal confirmation of toolchain versions.",
            ),
            OnboardingTask(
                task_id="DEV-02",
                order=2,
                title="Repository Access",
                description="Clone primary project repository and initialize local environment configuration.",
                category="Repository Access",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="Local repository cloned with dependencies installed.",
            ),
            OnboardingTask(
                task_id="DEV-03",
                order=3,
                title="Run Local Application",
                description="Start local services via Docker Compose and verify test suite passes.",
                category="Service Execution",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="Local services running and health checks green.",
            ),
            OnboardingTask(
                task_id="DEV-04",
                order=4,
                title="Architecture & Domain Review",
                description="Review KB-003 System Architecture documentation covering data flows, authentication, and service boundaries.",
                category="Architecture Review",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="Summary of system architecture and component interactions.",
            ),
            OnboardingTask(
                task_id="DEV-05",
                order=5,
                title="Engineering Standards Review",
                description="Read KB-002 Engineering Standards covering code style, testing requirements, and Git PR workflows.",
                category="API Standards",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="Acknowledgment of engineering quality standards.",
            ),
            OnboardingTask(
                task_id="DEV-06",
                order=6,
                title="Starter Task",
                description="Pick up starter ticket from team backlog, implement changes with tests, and open PR.",
                category="First Task",
                required=True,
                status="Pending",
                role=clean_role,
                technology=tech_name,
                evidence_required="GitHub PR link submitted for team review.",
            ),
        ]

    plan = OnboardingPlan(
        plan_id=f"plan-{session_key[:8]}",
        session_id=session_key,
        role=clean_role,
        experience_level=clean_level,
        technology_stack=stack,
        team=team_name,
        tasks=tasks,
        total_tasks=len(tasks),
        created_at=datetime.now(timezone.utc),
    )

    return plan


# Tasks in these states with no recorded evidence have never been worked on.
UNTOUCHED_STATUSES = ("Not Started", "Pending")


def persist_onboarding_plan(db: Session, session_id: str, plan: OnboardingPlan) -> None:
    """
    Make `plan` the session's checklist.

    Idempotent: updates existing tasks or inserts new ones without losing progress.
    Re-planning (e.g. the generic signup plan replaced once the persona is known)
    removes tasks from the previous plan that were never touched; tasks with any
    progress or evidence are kept so no user work is discarded.
    """
    plan_ids = {f"{session_id}::{task.task_id}" for task in plan.tasks}
    stale = db.query(models.ChecklistItemDB).filter(
        models.ChecklistItemDB.session_id == session_id,
        models.ChecklistItemDB.status.in_(UNTOUCHED_STATUSES),
    ).all()
    for item in stale:
        normalized = item.id if "::" in item.id else f"{session_id}::{item.id}"
        if normalized not in plan_ids and not item.completion_evidence:
            db.delete(item)

    for task in plan.tasks:
        db_item_id = f"{session_id}::{task.task_id}"

        existing = db.query(models.ChecklistItemDB).filter(
            (models.ChecklistItemDB.id == db_item_id) |
            ((models.ChecklistItemDB.session_id == session_id) & (models.ChecklistItemDB.id == task.task_id))
        ).first()

        if existing:
            # Preserve completed status and evidence if already marked
            if existing.status in ("Completed", "In Progress", "Blocked", "Skipped"):
                task.status = existing.status
                task.completed_at = existing.completed_at
                task.completion_evidence = existing.completion_evidence
                task.completion_source = existing.completion_source
            else:
                existing.task = f"{task.title}: {task.description}"
                existing.category = task.category
                existing.owner = "Employee"
                existing.deadline = f"Step {task.order}"
        else:
            new_item = models.ChecklistItemDB(
                id=db_item_id,
                session_id=session_id,
                task=f"{task.title}: {task.description}",
                category=task.category,
                owner="Employee",
                deadline=f"Step {task.order}",
                status=task.status,
                completion_evidence=task.completion_evidence,
                completed_at=task.completed_at,
                completion_source=task.completion_source,
            )
            db.add(new_item)

    db.commit()
    logger.info("Persisted personalized onboarding plan for session %s (%d tasks)", session_id, len(plan.tasks))


def apply_onboarding_plan(
    db: Session,
    session_id: str,
    role: str,
    experience_level: str,
    technology_stack: Optional[List[str]] = None,
    team: Optional[str] = None,
) -> OnboardingPlan:
    """Generate the personalized plan for this profile and make it the session's checklist."""
    plan = generate_onboarding_plan(
        role=role,
        experience_level=experience_level,
        technology_stack=technology_stack,
        team=team,
        session_id=session_id,
    )
    persist_onboarding_plan(db, session_id, plan)
    return plan


def get_plan_tasks_for_session(db: Session, session_id: str) -> List[Dict[str, Any]]:
    """Retrieve persisted tasks for a session formatted for agent state and UI."""
    items = db.query(models.ChecklistItemDB).filter(
        models.ChecklistItemDB.session_id == session_id
    ).all()

    tasks = []
    for item in items:
        clean_id = item.id.split("::")[-1] if "::" in item.id else item.id
        title = item.task.split(":", 1)[0] if ":" in item.task else item.task
        desc = item.task.split(":", 1)[1].strip() if ":" in item.task else item.task
        tasks.append({
            "task_id": clean_id,
            "id": clean_id,
            "title": title,
            "task": item.task,
            "description": desc,
            "category": item.category or "Onboarding",
            "owner": item.owner or "Employee",
            "deadline": item.deadline or "N/A",
            "status": item.status or "Pending",
            "required": True,
            "completion_evidence": item.completion_evidence,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "completion_source": item.completion_source,
        })
    return tasks
