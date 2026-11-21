from typing import Any, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# GitHub Schemas
# ============================================================================

class GitHubCreateIssueInput(BaseModel):
    title: str = Field(..., description="Title of the issue or starter task")
    description: str = Field("", description="Detailed body/description of the issue")
    repo_name: str = Field("backend-starter", description="Target repository name")
    org_name: str = Field("NovaByte-AI", description="Organization name")


class GitHubCreateIssueOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    ticket_id: str = Field(..., description="Unique ticket/issue identifier")
    url: Optional[str] = Field(None, description="Direct URL to the created issue")
    mode: str = Field("mock", description="'mock' or 'real'")
    error: Optional[str] = Field(None, description="Error message if failed")


class GitHubVerifyRepoAccessInput(BaseModel):
    repo_name: str = Field(..., description="Repository name to verify")
    github_handle: Optional[str] = Field(None, description="GitHub username to verify access for")
    org_name: str = Field("NovaByte-AI", description="Organization name")


class GitHubVerifyRepoAccessOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    accessible: bool = Field(..., description="Whether the repository is accessible")
    repo_name: str = Field(..., description="Target repository")
    mode: str = Field("mock", description="'mock' or 'real'")
    error: Optional[str] = Field(None, description="Error details if verification failed")


class GitHubInviteInput(BaseModel):
    github_handle: str = Field(..., description="GitHub username to invite")
    org_name: str = Field("NovaByte-AI", description="Organization name")


class GitHubGrantAccessInput(BaseModel):
    github_handle: str = Field(..., description="GitHub username")
    repo_name: str = Field(..., description="Target repository")
    permission: str = Field("pull", description="Permission level: pull, push, admin")
    org_name: str = Field("NovaByte-AI", description="Organization name")


# ============================================================================
# Email Schemas
# ============================================================================

class EmailCompletionReportInput(BaseModel):
    session_id: str = Field(..., description="Onboarding session ID")
    recipient: Optional[str] = Field(None, description="Recipient email (defaults to HR_EMAIL)")
    name: Optional[str] = Field(None, description="Employee name")
    role: Optional[str] = Field(None, description="Role")
    team: Optional[str] = Field(None, description="Assigned team")
    experience_level: Optional[str] = Field(None, description="Experience level")
    tech_stack: Optional[List[str]] = Field(default_factory=list, description="Technology stack")
    completed_items: Optional[List[Any]] = Field(default_factory=list, description="Completed tasks")
    pending_items: Optional[List[Any]] = Field(default_factory=list, description="Pending tasks")
    ticket: Optional[str] = Field(None, description="Starter ticket reference")
    confidence_score: Optional[float] = Field(None, description="Confidence score percentage")
    verification_info: Optional[str] = Field(None, description="Verification details")


class EmailCompletionReportOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    recipient: str = Field(..., description="Recipient email address")
    mode: str = Field("mock", description="'mock' or 'real'")
    file: Optional[str] = Field(None, description="Local file path for mock preview")
    error: Optional[str] = Field(None, description="Error message if failed")


class EmailWelcomeInput(BaseModel):
    recipient: str = Field(..., description="Employee email address")
    name: Optional[str] = Field("Team Member", description="Employee name")
    role: Optional[str] = Field("Developer", description="Employee role")
    body: Optional[str] = Field(None, description="Optional custom body text")


class EmailWelcomeOutput(BaseModel):
    status: str = Field(..., description="'success' or 'error'")
    recipient: str = Field(..., description="Recipient email address")
    mode: str = Field("mock", description="'mock' or 'real'")
    file: Optional[str] = Field(None, description="Local file path for mock preview")
    error: Optional[str] = Field(None, description="Error message if failed")
