# filename: src/models.py
"""Pydantic models for Actor input and output."""

from typing import Optional
from pydantic import BaseModel, Field


class ActorInput(BaseModel):
    """Input model for the Actor."""
    industry: str = Field(..., description="Industry to search for")
    location: str = Field(..., description="Location to search in")
    max_results: int = Field(default=50, ge=1, le=1000, description="Maximum number of results")


class OutputCompany(BaseModel):
    """Output model for company data."""
    company_name: str
    website_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    social_links: list[str] = Field(default_factory=list)
    company_size: Optional[str] = None
    company_address: Optional[str] = None
    company_emails: list[str] = Field(default_factory=list)

