#!/usr/bin/env python3
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import browser-use
import sys
sys.path.append('/Users/squash/Local/Code/bu/browser-use')
from browser_use import Agent, BrowserSession
from browser_use.browser.browser import Browser, BrowserConfig

app = FastAPI(title="Contact-Use API")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ContactSearchRequest(BaseModel):
    keywords: str
    organization: Optional[str] = None
    location: Optional[str] = None
    role: Optional[str] = None
    fields_to_find: List[str] = Field(default_factory=list)

class ContactResult(BaseModel):
    full_name: Optional[str] = None
    city: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    email: Optional[str] = None
    company_phone_number: Optional[str] = None
    contact_form_url: Optional[str] = None
    profile_image_url: Optional[str] = None
    cv_url: Optional[str] = None
    github_profile_url: Optional[str] = None
    twitter_profile_url: Optional[str] = None
    linkedin_profile_url: Optional[str] = None

class QueryStatus(BaseModel):
    id: str
    request: ContactSearchRequest
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[ContactResult] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

# In-memory storage for queries
queries: Dict[str, QueryStatus] = {}

# Background task executor
async def run_browser_search(query_id: str):
    query = queries[query_id]
    query.status = "running"
    
    try:
        # Build the task description
        task_parts = ["Find this contact info by any means necessary, take as long as you need and don't give up."]
        
        task_parts.append(f"\nSearch keywords: {query.request.keywords}")
        
        if query.request.organization:
            task_parts.append(f"Organization: {query.request.organization}")
        if query.request.location:
            task_parts.append(f"Location: {query.request.location}")
        if query.request.role:
            task_parts.append(f"Role/Job Title: {query.request.role}")
        
        task_parts.append("\nFind the following information:")
        for field in query.request.fields_to_find:
            task_parts.append(f"- {field.replace('_', ' ').title()}")
        
        task_parts.append("\nReturn the results in a structured format with the field names exactly as requested.")
        
        task = " ".join(task_parts)
        
        # Create browser session
        user_data_dir = Path.home() / '.config' / 'browseruse' / 'profiles' / 'default'
        session = BrowserSession(
            user_data_dir=str(user_data_dir),
            headless=False
        )
        
        # Create browser and agent
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                new_context_config={
                    'storage_state': None,
                    'user_data_dir': str(user_data_dir)
                }
            )
        )
        
        agent = Agent(
            task=task,
            browser=browser
        )
        
        # Run the search
        result = await agent.run()
        
        # Parse the result - the agent should return structured data
        # For now, we'll just store the raw result
        query.result = ContactResult()
        if isinstance(result, str):
            # Simple parsing - in practice, you'd want more sophisticated parsing
            result_lower = result.lower()
            if "email:" in result_lower or "@" in result:
                # Extract email if present
                import re
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', result)
                if email_match:
                    query.result.email = email_match.group(0)
            
            # You can add more parsing logic here based on the agent's response format
            
        query.status = "completed"
        query.completed_at = datetime.now()
        
    except Exception as e:
        query.status = "failed"
        query.error = str(e)
        query.completed_at = datetime.now()

@app.post("/api/search", response_model=QueryStatus)
async def create_search(request: ContactSearchRequest):
    """Create a new contact search query"""
    query_id = str(uuid.uuid4())
    
    query = QueryStatus(
        id=query_id,
        request=request,
        status="pending",
        created_at=datetime.now()
    )
    
    queries[query_id] = query
    
    # Start the search in the background
    asyncio.create_task(run_browser_search(query_id))
    
    return query

@app.get("/api/queries", response_model=List[QueryStatus])
async def get_all_queries():
    """Get all search queries"""
    return list(queries.values())

@app.get("/api/queries/{query_id}", response_model=QueryStatus)
async def get_query(query_id: str):
    """Get a specific search query by ID"""
    if query_id not in queries:
        raise HTTPException(status_code=404, detail="Query not found")
    return queries[query_id]

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)